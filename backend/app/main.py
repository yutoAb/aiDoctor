from flask import Flask, jsonify, request
from flask_cors import CORS
import os

def create_app():
    app = Flask(__name__)
    CORS(app, resources={r"/api/*": {"origins": "*"}})  # 開発中は * でOK。運用では限定推奨

    @app.get("/api/health")
    def health():
        return jsonify(status="ok", service="flask-backend")

    # サンプル: ToDo の簡易メモリ API（DB の代わりにメモリ保持）
    TODOS = [{"id": 1, "title": "first task"}]

    @app.get("/api/todos")
    def list_todos():
        return jsonify(TODOS)

    @app.post("/api/todos")
    def create_todo():
        data = request.get_json(force=True)
        if not data or "title" not in data:
            return jsonify(error="title is required"), 400
        new_id = (max([t["id"] for t in TODOS]) + 1) if TODOS else 1
        todo = {"id": new_id, "title": data["title"]}
        TODOS.append(todo)
        return jsonify(todo), 201

    return app

app = create_app()

if __name__ == "__main__":
    # ローカルで直接起動する場合用（Docker では command で起動）
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)
