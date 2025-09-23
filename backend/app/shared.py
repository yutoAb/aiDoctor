# app/shared.py
from __future__ import annotations
import os, json, time
from typing import Iterable, List
from pathlib import Path
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from openai import OpenAI

# ==== OpenAI ====
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# ==== DB ====
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@db:5432/appdb")
engine = sa.create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)
metadata = sa.MetaData()

encounter_table = sa.Table(
    "encounter",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("chief_complaint", sa.Text, nullable=True),
    sa.Column("status", sa.Text, nullable=False, server_default=sa.text("'active'")),
    sa.Column("started_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column("ended_at", sa.TIMESTAMP(timezone=True), nullable=True),
)

message_table = sa.Table(
    "message",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("encounter_id", sa.Text, sa.ForeignKey("encounter.id", ondelete="CASCADE"), nullable=False),
    sa.Column("role", sa.Text, nullable=False),
    sa.Column("content", sa.Text, nullable=False),
    sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column("meta", sa.dialects.postgresql.JSONB if engine.dialect.name == "postgresql" else sa.JSON, nullable=True),
)
sa.Index("idx_message_encounter_time", message_table.c.encounter_id, message_table.c.created_at)

def init_db():
    metadata.create_all(engine)

def encounter_exists(session, enc_id: str) -> bool:
    row = session.execute(sa.select(encounter_table.c.id).where(encounter_table.c.id == enc_id)).first()
    return row is not None

def load_messages_for_encounter(session, enc_id: str) -> List[dict]:
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

def system_prompt() -> dict:
    content = (
        "あなたは症状聴取を行う医師ボットです。診断は行わず、危険サインがあれば受診勧奨を行います。"
        "過度な断定は避け、分かりやすく短い文で質問を重ねてください。"
        "緊急性が高い可能性（激しい胸痛、呼吸困難、意識障害 等）がある場合は直ちに119番通報を案内してください。"
    )
    return {"role": "system", "content": content}

def to_openai_messages(history_msgs: List[dict]) -> List[dict]:
    msgs: List[dict] = [system_prompt()]
    for m in history_msgs:
        if m["role"] in ("system", "user", "assistant"):
            msgs.append({"role": m["role"], "content": m["content"]})
    return msgs

def sse(event: str, data: dict | str) -> str:
    payload = json.dumps(data, ensure_ascii=False) if isinstance(data, (dict, list)) else str(data)
    return f"event: {event}\ndata: {payload}\n\n"

def dummy_stream_answer(prompt_tail: str) -> Iterable[str]:
    text = (
        "それはいつ頃から、どのような状況で症状が出ますか？\n"
        "痛みの強さ（0〜10）、持続時間、増悪・寛解因子（動くと痛い/安静で軽くなる等）も教えてください。"
    )
    for ch in text:
        time.sleep(0.02)
        yield ch
