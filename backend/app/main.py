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

# ── OpenAI (任意) ───────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")  # 任意のモデル名

try:
    if OPENAI_API_KEY:
        # openai >= 1.x 系
        from openai import OpenAI
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
    else:
        openai_client = None
except Exception:
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
    単純にテンプレ応答を100ms刻みでトークン風に返す。
    """
    text = (
        "それはいつ頃から、どのような状況で症状が出ますか？\n"
        "痛みの強さ（0〜10）、持続時間、増悪・寛解因子（動くと痛い/安静で軽くなる等）も教えてください。"
    )
    for ch in text:
        time.sleep(0.03)
        yield ch


def create_app():
    app = Flask(__name__)
    # /consult/* と /api/* を CORS 許可
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

    # --- 診察セッション作成 ---
    @app.post("/consult/new")
    def create_encounter():
        """
        新しい診察セッションを作成し、encounter_id を返す。
        """
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

    # === 追加1) 初手テンプレ ===
    @app.get("/api/templates/first-message")
    def first_message():
        # 必要ならDB化/ロケール対応可
        return jsonify({"content": "本日はどうなさいましたか？", "locale": "ja-JP"})

    # === 追加2) ユーザ発言を保存 ===
    @app.post("/api/encounters/<encounter_id>/messages")
    def post_message(encounter_id: str):
        """
        ユーザ/システムの発言を保存する（role: 'user' か 'system' を想定）。
        応答生成自体は /stream 側で実施する想定。
        """
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

        # ここでは保存のみ。フロントはこの後 /stream を開いて応答を受け取る
        return jsonify({"message_id": msg_id, "status": "queued"}), 200

    # === 追加3) ストリーミング応答（SSE） ===
    @app.get("/api/encounters/<encounter_id>/stream")
    def stream_answer(encounter_id: str):
        """
        直近までの履歴をもとに、assistant応答をSSEでストリームし、完了後にDBへ保存。
        event: token で {"delta": "..."} を複数回、最後に event: done で {"messageId": "..."} を送る。
        """
        def generate() -> Iterable[str]:
            with SessionLocal() as session:
                if not _encounter_exists(session, encounter_id):
                    yield _sse("error", {"message": f"encounter {encounter_id} not found"})
                    return

                # 直近履歴を読み込み（system含む既存のもの）
                history = _load_messages_for_encounter(session, encounter_id)
                openai_msgs = _to_openai_messages(history)

                # OpenAI でストリーム or ダミー
                assistant_full = []
                try:
                    if openai_client is not None:
                        # Chat Completions (stream)
                        # openai>=1.x 例: client.chat.completions.create(...)
                        stream = openai_client.chat.completions.create(
                            model=OPENAI_MODEL,
                            messages=openai_msgs,
                            temperature=0.3,
                            stream=True,
                        )
                        for chunk in stream:
                            # choices[0].delta.content の断片を取り出す
                            delta = ""
                            try:
                                delta = chunk.choices[0].delta.content or ""
                            except Exception:
                                delta = ""
                            if delta:
                                assistant_full.append(delta)
                                yield _sse("token", {"delta": delta})
                    else:
                        # ダミーストリーム
                        for ch in _dummy_stream_answer(history[-1]["content"] if history else ""):
                            assistant_full.append(ch)
                            yield _sse("token", {"delta": ch})

                    # 応答を保存
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
                    # 途中エラーでもストリームを閉じれるように
                    yield _sse("error", {"message": f"stream failed: {e.__class__.__name__}"})

        return Response(stream_with_context(generate()), mimetype="text/event-stream")

    return app


app = create_app()

if __name__ == "__main__":
    # ローカル実行
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)
