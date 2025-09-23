from flask import Flask, jsonify, request
from flask_cors import CORS
from flasgger import Swagger
import os
import yaml
from pathlib import Path
import uuid

# ── DB: SQLAlchemy(Core) セットアップ ───────────────────────────
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

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

def init_db():
    metadata.create_all(engine)


def create_app():
    app = Flask(__name__)
    # /consult/* を CORS 許可
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

    # --- 診察セッション作成エンドポイント ---
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

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)
