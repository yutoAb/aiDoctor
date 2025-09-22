FROM python:3.11-slim

# システム更新 & 便利ツール
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    build-essential curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 依存関係インストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリ本体
COPY app ./app

# 本番用に Gunicorn を使いたい場合は以下を ON に（後述）
# RUN pip install gunicorn==21.2.0

ENV FLASK_APP=app.main

# デバッグ起動（開発想定）。本番は gunicorn 推奨（後述）
CMD ["flask", "--app", "app.main", "run", "--host=0.0.0.0", "--port=5000", "--debug"]
