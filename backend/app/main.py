from flask import Flask, jsonify, request
from flask_cors import CORS
from flasgger import Swagger
import os
import yaml
from pathlib import Path

# ── DB: SQLAlchemy(Core) セットアップ ───────────────────────────
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

# 環境変数から接続文字列を取得（compose.yml/.env と合わせる）
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@db:5432/appdb",
)

# 2.0 スタイル
engine = sa.create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)

metadata = sa.MetaData()
todos_table = sa.Table(
    "todos",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("title", sa.Text, nullable=False),
)

# アプリ起動時にテーブルを作成（存在しなければ）
def init_db():
    metadata.create_all(engine)


def create_app():
    app = Flask(__name__)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # --- Swagger 設定読み込み ---
    with open(Path(__file__).with_name("swagger.yml"), encoding="utf-8") as f:
        swagger_template = yaml.safe_load(f)
    swagger = Swagger(app, template=swagger_template)

    # 起動時に DB 初期化
    init_db()

    @app.get("/api/health")
    def health():
        # DB疎通も軽く確認（失敗しても 200 を返したい場合は try/except でstatusを分ける）
        try:
            with engine.connect() as conn:
                conn.execute(sa.text("SELECT 1"))
            db_status = "ok"
        except Exception as e:
            db_status = f"ng: {e.__class__.__name__}"
        return jsonify(status="ok", service="flask-backend", db=db_status)

    # --- ToDo API（DB版） ---
    @app.get("/api/todos")
    def list_todos():
        with SessionLocal() as session:
            rows = session.execute(
                sa.select(todos_table.c.id, todos_table.c.title).order_by(todos_table.c.id)
            ).all()
            data = [{"id": r.id, "title": r.title} for r in rows]
        return jsonify(data)

    @app.post("/api/todos")
    def create_todo():
        data = request.get_json(force=True)
        if not data or "title" not in data or not str(data["title"]).strip():
            return jsonify(error="title is required"), 400

        title = str(data["title"]).strip()
        with SessionLocal() as session:
            # INSERT ... RETURNING id
            result = session.execute(
                sa.insert(todos_table).values(title=title).returning(todos_table.c.id)
            )
            new_id = result.scalar_one()
            session.commit()

        return jsonify({"id": new_id, "title": title}), 201
    
    @app.delete("/api/todos/<int:todo_id>")
    def delete_todo(todo_id: int):
        with SessionLocal() as session:
            # DELETE ... RETURNING id で存在確認も兼ねる
            result = session.execute(
                sa.delete(todos_table)
                .where(todos_table.c.id == todo_id)
                .returning(todos_table.c.id)
            )
            deleted_id = result.scalar_one_or_none()
            if deleted_id is None:
                # 存在しないID
                return jsonify(error=f"todo id={todo_id} not found"), 404

            session.commit()
        # 成功時は本体なしで204を返す
        return ("", 204)

    return app


app = create_app()

if __name__ == "__main__":
    # ローカルで直接起動する場合用（Docker では command で起動）
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)