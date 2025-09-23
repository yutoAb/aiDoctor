# app/main.py
from __future__ import annotations
from flask import Flask, jsonify, request, Response, stream_with_context
from flask_cors import CORS
from flasgger import Swagger
import os, yaml, uuid
from pathlib import Path
import sqlalchemy as sa

from app.shared import (
    init_db, engine, SessionLocal,
    encounter_table, message_table,
    to_openai_messages, sse, dummy_stream_answer,
    openai_client, OPENAI_MODEL, encounter_exists, load_messages_for_encounter
)
from app.routes.clinical_note import bp as clinical_note_bp

def create_app():
    app = Flask(__name__)
    CORS(app,
         resources={r"/consult/*": {"origins": "*"}, r"/api/*": {"origins": "*"}},
         allow_headers=["Content-Type", "Authorization"],
         expose_headers=["Content-Type"],
         methods=["GET", "POST", "OPTIONS"])

    swagger_file = Path(__file__).with_name("swagger.yml")
    if swagger_file.exists():
        with open(swagger_file, encoding="utf-8") as f:
            Swagger(app, template=yaml.safe_load(f))

    init_db()

    @app.get("/api/health")
    def health():
        try:
            with engine.connect() as conn:
                conn.execute(sa.text("SELECT 1"))
            db_status = "ok"
        except Exception as e:
            db_status = f"ng: {e.__class__.__name__}"
        return jsonify(status="ok", service="flask-backend", db=db_status)

    @app.get("/api/encounters")
    def list_encounters():
        status = request.args.get("status")
        try:
            limit = max(1, min(int(request.args.get("limit", 50)), 200))
        except ValueError:
            limit = 50
        try:
            offset = max(0, int(request.args.get("offset", 0)))
        except ValueError:
            offset = 0

        stmt = sa.select(
            encounter_table.c.id,
            encounter_table.c.chief_complaint,
            encounter_table.c.status,
            encounter_table.c.started_at,
            encounter_table.c.ended_at,
        ).order_by(encounter_table.c.started_at.desc())

        if status in ("active", "closed"):
            stmt = stmt.where(encounter_table.c.status == status)

        stmt = stmt.limit(limit).offset(offset)

        with SessionLocal() as session:
            rows = session.execute(stmt).all()

        def to_camel(r):
            return {
                "id": r.id,
                "chiefComplaint": r.chief_complaint,
                "status": r.status,
                "startedAt": (r.started_at.isoformat() if r.started_at else None),
                "endedAt": (r.ended_at.isoformat() if r.ended_at else None),
                "triageLevel": None,
                "needsAttention": False,
            }

        return jsonify([to_camel(r) for r in rows])

    @app.post("/consult/new")
    def create_encounter():
        payload = request.get_json(silent=True) or {}
        chief_complaint = payload.get("chief_complaint")
        enc_id = str(uuid.uuid4())
        with SessionLocal() as session:
            session.execute(sa.insert(encounter_table).values(
                id=enc_id, chief_complaint=chief_complaint, status="active"
            ))
            session.commit()
        return jsonify({"encounter_id": enc_id}), 201

    @app.get("/api/templates/first-message")
    def first_message():
        return jsonify({"content": "本日はどうなさいましたか？", "locale": "ja-JP"})

    @app.post("/api/encounters/<encounter_id>/messages")
    def post_message(encounter_id: str):
        payload = request.get_json(force=True)
        role = payload.get("role")
        content = (payload.get("content") or "").trim() if hasattr(str, "trim") else (payload.get("content") or "").strip()

        if role not in ("user", "system"):
            return jsonify(error="role must be 'user' or 'system'"), 400
        if not content:
            return jsonify(error="content is required"), 400

        with SessionLocal() as session:
            if not encounter_exists(session, encounter_id):
                return jsonify(error=f"encounter {encounter_id} not found"), 404
            msg_id = str(uuid.uuid4())
            session.execute(sa.insert(message_table).values(
                id=msg_id, encounter_id=encounter_id, role=role, content=content
            ))
            session.commit()
        return jsonify({"message_id": msg_id, "status": "queued"}), 200

    @app.post("/api/encounters/<encounter_id>/end")
    def end_encounter(encounter_id: str):
        with SessionLocal() as session:
            if not encounter_exists(session, encounter_id):
                return jsonify(error=f"encounter {encounter_id} not found"), 404
            session.execute(
                sa.update(encounter_table)
                .where(encounter_table.c.id == encounter_id)
                .values(status="closed", ended_at=sa.func.now())
            )
            session.commit()
        return jsonify({"status": "closed"}), 200

    @app.get("/api/encounters/<encounter_id>/stream")
    def stream_answer(encounter_id: str):
        def generate():
            with SessionLocal() as session:
                if not encounter_exists(session, encounter_id):
                    yield sse("error", {"message": f"encounter {encounter_id} not found"})
                    return

                history = load_messages_for_encounter(session, encounter_id)
                openai_msgs = to_openai_messages(history)

                assistant_full = []
                try:
                    if openai_client is not None:
                        stream = openai_client.chat.completions.create(
                            model=OPENAI_MODEL, messages=openai_msgs, temperature=0.3, stream=True
                        )
                        for chunk in stream:
                            delta = ""
                            try:
                                delta = chunk.choices[0].delta.content or ""
                            except Exception:
                                delta = ""
                            if delta:
                                assistant_full.append(delta)
                                yield sse("token", {"delta": delta})
                    else:
                        last = history[-1]["content"] if history else ""
                        for ch in dummy_stream_answer(last):
                            assistant_full.append(ch)
                            yield sse("token", {"delta": ch})

                    final_text = "".join(assistant_full).strip()
                    msg_id = str(uuid.uuid4())
                    session.execute(sa.insert(message_table).values(
                        id=msg_id, encounter_id=encounter_id, role="assistant",
                        content=final_text or "（応答が生成できませんでした）",
                        meta={"model": OPENAI_MODEL} if openai_client else {"model": "dummy"},
                    ))
                    session.commit()
                    yield sse("done", {"messageId": msg_id})
                except Exception as e:
                    yield sse("error", {"message": f"stream failed: {e.__class__.__name__}"})

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
        )

    app.register_blueprint(clinical_note_bp)
    return app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)
