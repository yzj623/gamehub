from __future__ import annotations

import os

from flask import Flask, jsonify, render_template

from config import Config
from routes import api


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    app.register_blueprint(api)

    os.makedirs(app.config["UPLOAD_DIR"], exist_ok=True)

    # Global error handler for API routes - ensure JSON responses
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "bad request"}), 400

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "not found"}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"error": "method not allowed"}), 405

    @app.errorhandler(413)
    def request_entity_too_large(e):
        return jsonify({"error": "request too large"}), 413

    @app.errorhandler(500)
    def internal_error(e):
        return jsonify({"error": "internal server error"}), 500

    @app.get("/")
    def home():
        return render_template("store.html")

    @app.get("/login")
    def login_page():
        return render_template("login.html")

    @app.get("/register")
    def register_page():
        return render_template("register.html")

    @app.get("/publisher")
    def publisher_page():
        return render_template("publisher.html")

    @app.get("/profile")
    def my_profile_page():
        return render_template("profile.html", user_id="me")

    @app.get("/profile/<int:user_id>")
    def profile_page(user_id: int):
        return render_template("profile.html", user_id=user_id)

    @app.get("/game/<int:game_id>")
    def game_page(game_id: int):
        return render_template("game.html", game_id=game_id)

    @app.get("/mail/<int:mail_id>")
    def mail_detail_page(mail_id: int):
        return render_template("mail_detail.html", mail_id=mail_id)

    @app.get("/chat/<int:friend_id>")
    def chat_page(friend_id: int):
        return render_template("chat.html", friend_id=friend_id)

    @app.get("/health")


    def health():
        return {"status": "ok"}

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=5000, debug=True)
