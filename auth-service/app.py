import os
import time
from datetime import datetime, timedelta, timezone

import jwt
from flask import Flask, jsonify, request
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import OperationalError


db = SQLAlchemy()
bcrypt = Bcrypt()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


def normalize_database_url(url: str) -> str:
    if url and url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg2://", 1)
    return url


def create_app(test_config=None):
    app = Flask(__name__)

    database_url = normalize_database_url(
        os.getenv("DATABASE_URL", "sqlite:///auth_service.db")
    )

    app.config.update(
        SQLALCHEMY_DATABASE_URI=database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        JWT_SECRET_KEY=os.getenv("JWT_SECRET_KEY", "dev-secret-change-me"),
        TESTING=False,
    )

    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    bcrypt.init_app(app)
    CORS(app)

    register_routes(app)

    if not app.config["TESTING"]:
        initialize_database(app)

    return app


def initialize_database(app):
    attempts = int(os.getenv("DB_INIT_ATTEMPTS", "30"))
    delay = float(os.getenv("DB_INIT_DELAY", "2"))

    with app.app_context():
        for attempt in range(1, attempts + 1):
            try:
                db.create_all()
                app.logger.info("Database initialized for auth-service.")
                return
            except OperationalError as exc:
                app.logger.warning(
                    "Database not ready for auth-service. Attempt %s/%s. Error: %s",
                    attempt,
                    attempts,
                    exc,
                )
                time.sleep(delay)

        raise RuntimeError("Database initialization failed for auth-service.")


def generate_token(user: User, secret: str) -> str:
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "exp": datetime.now(timezone.utc) + timedelta(hours=8),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_token(token: str, secret: str):
    return jwt.decode(token, secret, algorithms=["HS256"])


def get_bearer_token():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    return auth_header.removeprefix("Bearer ").strip()


def register_routes(app):
    @app.get("/auth/health")
    def health():
        return jsonify({"status": "ok", "service": "auth-service"})

    @app.post("/auth/register")
    def register():
        data = request.get_json(silent=True) or {}
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""

        if not username or not password:
            return jsonify({"error": "Login i hasło są wymagane."}), 400

        if len(password) < 4:
            return jsonify({"error": "Hasło musi mieć co najmniej 4 znaki."}), 400

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return jsonify({"error": "Użytkownik o takim loginie już istnieje."}), 409

        password_hash = bcrypt.generate_password_hash(password).decode("utf-8")
        user = User(username=username, password_hash=password_hash)

        db.session.add(user)
        db.session.commit()

        return jsonify({
            "message": "Użytkownik został zarejestrowany.",
            "user_id": user.id,
            "username": user.username,
        }), 201

    @app.post("/auth/login")
    def login():
        data = request.get_json(silent=True) or {}
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""

        if not username or not password:
            return jsonify({"error": "Login i hasło są wymagane."}), 400

        user = User.query.filter_by(username=username).first()

        if not user or not bcrypt.check_password_hash(user.password_hash, password):
            return jsonify({"error": "Nieprawidłowy login lub hasło."}), 401

        token = generate_token(user, app.config["JWT_SECRET_KEY"])

        return jsonify({
            "message": "Zalogowano.",
            "token": token,
            "user_id": user.id,
            "username": user.username,
        })

    @app.post("/auth/verify")
    def verify():
        token = get_bearer_token()
        if not token:
            return jsonify({"valid": False, "error": "Brak tokenu."}), 401

        try:
            payload = decode_token(token, app.config["JWT_SECRET_KEY"])
        except jwt.ExpiredSignatureError:
            return jsonify({"valid": False, "error": "Token wygasł."}), 401
        except jwt.InvalidTokenError:
            return jsonify({"valid": False, "error": "Nieprawidłowy token."}), 401

        return jsonify({
            "valid": True,
            "user_id": payload["sub"],
            "username": payload["username"],
        })


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
