# app/routes/clinical_note.py
from __future__ import annotations
from flask import Blueprint, jsonify, request
from datetime import datetime

from app.shared import (
    SessionLocal, encounter_table, message_table,
    load_messages_for_encounter, encounter_exists,
    openai_client, OPENAI_MODEL
)

bp = Blueprint("clinical_note", __name__)

SYSTEM_PROMPT = """あなたは日本の内科医です。以下の対話履歴をもとに、医療現場で使える簡潔で網羅的なカルテ（Markdown）を作成します。
- 日本語、見出し付き(Markdown)
- 主訴(CC)、現病歴(HPI)、既往歴、アレルギー、内服薬、生活歴/家族歴(分かる範囲)、バイタル(不明なら「未測定」)、身体所見(対話から抽出/推定)、鑑別診断、評価(Assessment)、計画(Plan: 検査/処方/指導/フォロー/受診目安)
- 対話にない箇所は「不明」や「未入力」で明記し、推測は明確に注記
- 緊急を要する可能性がある所見はPlan内に注意喚起
"""

@bp.post("/api/encounters/<encounter_id>/clinical-note")
def generate_clinical_note(encounter_id: str):
    with SessionLocal() as session:
        if not encounter_exists(session, encounter_id):
            return jsonify(error=f"encounter {encounter_id} not found"), 404

        # 会話履歴を時系列で取得し、素朴にテキスト化
        rows = load_messages_for_encounter(session, encounter_id)
        convo_lines = []
        for m in rows:
            who = "患者" if m["role"] == "user" else ("AI" if m["role"] == "assistant" else "システム")
            # created_at はここでは返していないため省略（必要ならSELECTを拡張）
            convo_lines.append(f"{who}: {m['content']}")
        convo = "\n".join(convo_lines)

        # 主訴（ざっくり抽出：最後の患者発言の先頭50字）
        last_user = None
        for m in reversed(rows):
            if m["role"] == "user":
                last_user = m["content"]
                break
        chief_complaint = (last_user or "")[:50] or None

        # OpenAI で Markdown カルテ生成（キーが無ければ簡易テンプレ）
        if openai_client:
            resp = openai_client.chat.completions.create(
                model=OPENAI_MODEL,
                temperature=0.2,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"【対話履歴】\n{convo}\n\n以上を踏まえて、見出し付きMarkdownの内科カルテを書いてください。"}
                ]
            )
            note_md = resp.choices[0].message.content
        else:
            note_md = (
                "# 内科カルテ\n\n"
                f"**主訴**: {chief_complaint or '（未入力）'}\n\n"
                "**現病歴**: （チャット内容をもとに要約）\n\n"
                "**既往歴**: \n\n"
                "**アレルギー**: \n\n"
                "**内服薬**: \n\n"
                "**身体所見**: \n\n"
                "**鑑別診断**: \n\n"
                "**評価**: \n\n"
                "**Plan**: 検査/処方/指導/フォローアップ\n\n"
                f"---\n作成時刻: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )

        return jsonify({
            "note_md": note_md,
            "chief_complaint": chief_complaint,
            "created_at": datetime.now().isoformat()
        }), 200
