FROM python:3.11-slim

# システム更新 & 便利ツール + PostgreSQLクライアントライブラリ
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    build-essential curl libpq-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 依存関係インストール（requirements.txt は psycopg2-binary を推奨）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリ本体
COPY app ./app

# 本番で Gunicorn を使う場合は有効化
# RUN pip install --no-cache-dir gunicorn==21.2.0

# 環境変数（compose 側からも上書き可）
ENV FLASK_APP=app.main

# デバッグ起動（本番は gunicorn 推奨）
CMD ["flask", "--app", "app.main", "run", "--host=0.0.0.0", "--port=5000", "--debug"]