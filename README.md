# aiDoctor

### エンドポイント

| フロントの呼び先                            | メソッド     | 実装場所                                             |
| ----------------------------------- | -------- | ------------------------------------------------ |
| `/api/templates/first-message`      | GET      | `main.py:first_message`                          |
| `/api/encounters/:id/messages`      | POST     | `main.py:post_message`                           |
| `/api/encounters/:id/stream`        | GET(SSE) | `main.py:stream_answer`                          |
| `/api/encounters/:id/end`           | POST     | `main.py:end_encounter`                          |
| `/api/encounters/:id/clinical-note` | POST     | `routes/clinical_note.py:generate_clinical_note` |
