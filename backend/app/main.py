from flask import Flask, jsonify, request, Response, stream_with_context
from flask_cors import CORS
from flasgger import Swagger
import os
import yaml
from pathlib import Path
import uuid
import json
import time
from typing import Iterable, List

# ── DB: SQLAlchemy(Core) セットアップ ───────────────────────────
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

# ── OpenAI（Chat Completions を使用） ──────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# デフォルトは安全に存在するモデル名を使用
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

openai_client = None
try:
    if OPENAI_API_KEY:
        from openai import OpenAI
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
        print("[BOOT] OPENAI_API_KEY set: True", flush=True)
        print(f"[BOOT] OpenAI client initialized. model={OPENAI_MODEL}", flush=True)
    else:
        print("[BOOT] OPENAI_API_KEY set: False → Using DUMMY stream", flush=True)
except Exception as e:
    print(f"[BOOT] OpenAI init failed: {e.__class__.__name__}: {e}", flush=True)
    openai_client = None

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@db:5432/appdb",
)

engine = sa.create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)

metadata = sa.MetaData()

# --- Encounter（診察セッション）テーブル ---
encounter_table = sa.Table(
    "encounter",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),  # UUID文字列
    sa.Column("chief_complaint", sa.Text, nullable=True),
    sa.Column("status", sa.Text, nullable=False, server_default=sa.text("'active'")),
    sa.Column("started_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column("ended_at", sa.TIMESTAMP(timezone=True), nullable=True),
)

# --- Message（会話ログ）テーブル ---
message_table = sa.Table(
    "message",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),  # UUID文字列
    sa.Column("encounter_id", sa.Text, sa.ForeignKey("encounter.id", ondelete="CASCADE"), nullable=False),
    sa.Column("role", sa.Text, nullable=False),  # 'system' | 'user' | 'assistant'
    sa.Column("content", sa.Text, nullable=False),
    sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column("meta", sa.dialects.postgresql.JSONB if engine.dialect.name == "postgresql" else sa.JSON, nullable=True),
)
sa.Index("idx_message_encounter_time", message_table.c.encounter_id, message_table.c.created_at)

def init_db():
    metadata.create_all(engine)


def _encounter_exists(session, enc_id: str) -> bool:
    row = session.execute(sa.select(encounter_table.c.id).where(encounter_table.c.id == enc_id)).first()
    return row is not None


def _load_messages_for_encounter(session, enc_id: str) -> List[dict]:
    rows = session.execute(
        sa.select(
            message_table.c.id,
            message_table.c.role,
            message_table.c.content,
            message_table.c.created_at,
        )
        .where(message_table.c.encounter_id == enc_id)
        .order_by(message_table.c.created_at.asc())
    ).all()
    return [{"id": r.id, "role": r.role, "content": r.content} for r in rows]


def _system_prompt() -> dict:
    # 医療安全のガードレール（簡易版）
    content = (
        "あなたは症状聴取を行う医師ボットです。診断は行わず、危険サインがあれば受診勧奨を行います。"
        "過度な断定は避け、分かりやすく短い文で質問を重ねてください。"
        "緊急性が高い可能性（激しい胸痛、呼吸困難、意識障害 等）がある場合は直ちに119番通報を案内してください。"
    )
    return {"role": "system", "content": content}


def _to_openai_messages(history_msgs: List[dict]) -> List[dict]:
    """
    DBから取り出した {role, content} の配列に、先頭へ system を加えた OpenAI 形式へ変換
    """
    msgs: List[dict] = [_system_prompt()]
    for m in history_msgs:
        role = m["role"]
        if role not in ("system", "user", "assistant"):
            continue
        msgs.append({"role": role, "content": m["content"]})
    return msgs


def _sse(event: str, data: dict | str) -> str:
    if isinstance(data, (dict, list)):
        payload = json.dumps(data, ensure_ascii=False)
    else:
        payload = str(data)
    return f"event: {event}\ndata: {payload}\n\n"


def _dummy_stream_answer(prompt_tail: str) -> Iterable[str]:
    """
    OpenAIキーが無い場合のダミーストリーム。
    単純にテンプレ応答を刻んで返す。
    """
    text = (
        "それはいつ頃から、どのような状況で症状が出ますか？\n"
        "痛みの強さ（0〜10）、持続時間、増悪・寛解因子（動くと痛い/安静で軽くなる等）も教えてください。"
    )
    for ch in text:
        time.sleep(0.02)
        yield ch


def create_app():
    app = Flask(__name__)
    CORS(app, resources={r"/consult/*": {"origins": "*"}, r"/api/*": {"origins": "*"}})

    # Swagger 読み込み
    swagger_file = Path(__file__).with_name("swagger.yml")
    if swagger_file.exists():
        with open(swagger_file, encoding="utf-8") as f:
            swagger_template = yaml.safe_load(f)
        Swagger(app, template=swagger_template)

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

    # === 追加: 診察セッション一覧 ===
    @app.get("/api/encounters")
    def list_encounters():
        """
        診察セッション一覧を返す。
        クエリ:
          - status: 'active' | 'closed'（任意）
          - limit:  1..200（任意・デフォルト50）
          - offset: 0..   （任意・デフォルト0）
        レスポンス（例）:
          [
            {
              "id": "enc_xxx",
              "chiefComplaint": "胸が痛い",
              "status": "active",
              "startedAt": "2025-09-23T03:25:00Z",
              "endedAt": null,
              "triageLevel": null,
              "needsAttention": false
            },
            ...
          ]
        """
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
            # triageLevel / needsAttention は今は未実装（null/false）で返す
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

    # --- 診察セッション作成 ---
    @app.post("/consult/new")
    def create_encounter():
        payload = request.get_json(silent=True) or {}
        chief_complaint = payload.get("chief_complaint")

        encounter_id = str(uuid.uuid4())
        with SessionLocal() as session:
            session.execute(
                sa.insert(encounter_table).values(
                    id=encounter_id,
                    chief_complaint=chief_complaint,
                    status="active",
                )
            )
            session.commit()

        return jsonify({"encounter_id": encounter_id}), 201

    # === 初手テンプレ ===
    @app.get("/api/templates/first-message")
    def first_message():
        return jsonify({"content": "本日はどうなさいましたか？", "locale": "ja-JP"})

    # === ユーザ発言を保存 ===
    @app.post("/api/encounters/<encounter_id>/messages")
    def post_message(encounter_id: str):
        payload = request.get_json(force=True)
        role = payload.get("role")
        content = (payload.get("content") or "").strip()

        if role not in ("user", "system"):
            return jsonify(error="role must be 'user' or 'system'"), 400
        if not content:
            return jsonify(error="content is required"), 400

        with SessionLocal() as session:
            if not _encounter_exists(session, encounter_id):
                return jsonify(error=f"encounter {encounter_id} not found"), 404

            msg_id = str(uuid.uuid4())
            session.execute(
                sa.insert(message_table).values(
                    id=msg_id,
                    encounter_id=encounter_id,
                    role=role,
                    content=content,
                )
            )
            session.commit()

        return jsonify({"message_id": msg_id, "status": "queued"}), 200

    # === ストリーミング応答（SSE） ===
    @app.get("/api/encounters/<encounter_id>/stream")
    def stream_answer(encounter_id: str):
        def generate():
            with SessionLocal() as session:
                if not _encounter_exists(session, encounter_id):
                    yield _sse("error", {"message": f"encounter {encounter_id} not found"})
                    return

                history = _load_messages_for_encounter(session, encounter_id)
                openai_msgs = _to_openai_messages(history)

                assistant_full = []
                try:
                    if openai_client is not None:
                        stream = openai_client.chat.completions.create(
                            model=OPENAI_MODEL,
                            messages=openai_msgs,
                            temperature=0.3,
                            stream=True,
                        )
                        for chunk in stream:
                            delta = ""
                            try:
                                delta = chunk.choices[0].delta.content or ""
                            except Exception:
                                delta = ""
                            if delta:
                                assistant_full.append(delta)
                                yield _sse("token", {"delta": delta})
                    else:
                        for ch in _dummy_stream_answer(history[-1]["content"] if history else ""):
                            assistant_full.append(ch)
                            yield _sse("token", {"delta": ch})

                    final_text = "".join(assistant_full).strip()
                    msg_id = str(uuid.uuid4())
                    session.execute(
                        sa.insert(message_table).values(
                            id=msg_id,
                            encounter_id=encounter_id,
                            role="assistant",
                            content=final_text or "（応答が生成できませんでした）",
                            meta={"model": OPENAI_MODEL} if openai_client else {"model": "dummy"},
                        )
                    )
                    session.commit()

                    yield _sse("done", {"messageId": msg_id})

                except Exception as e:
                    yield _sse("error", {"message": f"stream failed: {e.__class__.__name__}"})

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
        )

    @app.get("/api/debug/openai")
    def debug_openai():
        if openai_client is None:
            return jsonify(ok=False, reason="client_not_initialized"), 200
        try:
            resp = openai_client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Say ping once in Japanese."},
                ],
                max_tokens=8,
                temperature=0.0,
            )
            text = resp.choices[0].message.content
            return jsonify(ok=True, sample=text), 200
        except Exception as e:
            return jsonify(ok=False, reason=f"{e.__class__.__name__}: {e}"), 200

    return app

app = create_app()

if __name__ == "__main__":
    # ローカル実行
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)
