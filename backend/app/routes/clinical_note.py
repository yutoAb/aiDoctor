# app/routes/clinical_note.py
from flask import Blueprint, jsonify, request
from datetime import datetime
from openai import OpenAI
import os

bp = Blueprint("clinical_note", __name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

SYSTEM_PROMPT = """あなたは日本の内科医です。以下の対話履歴をもとに、医療現場で使える簡潔で網羅的なカルテ（Markdown）を作成します。
- 日本語、見出し付き(Markdown)
- 主訴(CC)、現病歴(HPI)、既往歴、アレルギー、内服薬、生活歴/家族歴(分かる範囲)、バイタル(不明なら「未測定」)、身体所見(対話から抽出/推定)、鑑別診断、評価(Assessment)、計画(Plan: 検査/処方/指導/フォロー/受診目安)
- 対話にない箇所は「不明」や「未入力」で明記し、推測は明確に注記
- 緊急を要する可能性がある所見はPlan内に注意喚起
"""

def build_user_content(encounter_id: str):
    # DBから対話を時系列で取得
    msgs = (
        Message.query.filter_by(encounter_id=encounter_id)
        .order_by(Message.created_at.asc())
        .all()
    )
    lines = []
    for m in msgs:
        who = "患者" if m.role == "user" else ("AI" if m.role == "assistant" else "システム")
        ts = m.created_at.strftime("%Y-%m-%d %H:%M")
        lines.append(f"[{ts}] {who}: {m.content}")
    return "\n".join(lines)

@bp.route("/api/encounters/<encounter_id>/clinical-note", methods=["POST"])
def generate_note(encounter_id):
    # 1) 会話をまとめる
    convo = build_user_content(encounter_id)
    if not convo.strip():
        return jsonify({"error": "no messages"}), 400

    # 2) 必要なら主訴をざっくり抽出（簡易）
    #   直近の患者メッセージから拾う等、ここは任意
    last_user = (
        Message.query.filter_by(encounter_id=encounter_id, role="user")
        .order_by(Message.created_at.desc())
        .first()
    )
    chief_complaint = last_user.content[:50] if last_user else None

    # 3) LLMへプロンプト
    resp = client.chat.completions.create(
        model=MODEL,
        temperature=0.2,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"【対話履歴】\n{convo}\n\n以上を踏まえて、見出し付きMarkdownの内科カルテを書いてください。"}
        ]
    )
    note_md = resp.choices[0].message.content

    # 4) 必要なら永続化（DBやS3等）
    # Encounter.query.filter_by(id=encounter_id).update({"note_md": note_md})
    # db.session.commit()

    return jsonify({
        "note_md": note_md,
        "chief_complaint": chief_complaint,
        "created_at": datetime.now().isoformat()
    }), 200
