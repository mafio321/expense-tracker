import os
import time
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import OperationalError


db = SQLAlchemy()


class Expense(db.Model):
    __tablename__ = "expenses"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(64), nullable=False, index=True)
    title = db.Column(db.String(120), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    category = db.Column(db.String(80), nullable=True)
    expense_date = db.Column(db.Date, nullable=True)
    description = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


def normalize_database_url(url: str) -> str:
    if url and url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg2://", 1)
    return url


def create_app(test_config=None):
    app = Flask(__name__)

    database_url = normalize_database_url(
        os.getenv("DATABASE_URL", "sqlite:///expense_service.db")
    )

    app.config.update(
        SQLALCHEMY_DATABASE_URI=database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        AUTH_SERVICE_URL=os.getenv("AUTH_SERVICE_URL", "http://auth-service:5000"),
        TESTING=False,
    )

    if test_config:
        app.config.update(test_config)

    db.init_app(app)
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
                app.logger.info("Database initialized for expense-service.")
                return
            except OperationalError as exc:
                app.logger.warning(
                    "Database not ready for expense-service. Attempt %s/%s. Error: %s",
                    attempt,
                    attempts,
                    exc,
                )
                time.sleep(delay)

        raise RuntimeError("Database initialization failed for expense-service.")


def validate_token():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, (jsonify({"error": "Brak tokenu autoryzacyjnego."}), 401)

    auth_service_url = os.getenv("AUTH_SERVICE_URL", "http://auth-service:5000")

    try:
        response = requests.post(
            f"{auth_service_url}/auth/verify",
            headers={"Authorization": auth_header},
            timeout=5,
        )
    except requests.RequestException:
        return None, (jsonify({"error": "Nie można połączyć się z auth-service."}), 503)

    if response.status_code != 200:
        return None, (jsonify({"error": "Nieprawidłowa autoryzacja."}), 401)

    data = response.json()
    return {
        "user_id": str(data["user_id"]),
        "username": data.get("username"),
    }, None


def parse_amount(value):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError):
        return None

    if amount <= 0:
        return None

    return amount.quantize(Decimal("0.01"))


def parse_date(value):
    if not value:
        return None

    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def expense_to_dict(expense: Expense):
    return {
        "id": expense.id,
        "user_id": expense.user_id,
        "title": expense.title,
        "amount": float(expense.amount),
        "category": expense.category,
        "expense_date": expense.expense_date.isoformat() if expense.expense_date else None,
        "description": expense.description,
        "created_at": expense.created_at.isoformat(),
    }


def register_routes(app):
    @app.get("/expenses/health")
    def health():
        return jsonify({"status": "ok", "service": "expense-service"})

    @app.get("/expenses")
    def list_expenses():
        user, error = validate_token()
        if error:
            return error

        expenses = (
            Expense.query
            .filter_by(user_id=user["user_id"])
            .order_by(Expense.created_at.desc())
            .all()
        )

        return jsonify([expense_to_dict(expense) for expense in expenses])

    @app.post("/expenses")
    def create_expense():
        user, error = validate_token()
        if error:
            return error

        data = request.get_json(silent=True) or {}
        title = (data.get("title") or "").strip()
        amount = parse_amount(data.get("amount"))
        expense_date = parse_date(data.get("expense_date"))
        category = (data.get("category") or "").strip() or None
        description = (data.get("description") or "").strip() or None

        if not title:
            return jsonify({"error": "Nazwa wydatku jest wymagana."}), 400

        if amount is None:
            return jsonify({"error": "Kwota musi być dodatnią liczbą."}), 400

        if data.get("expense_date") and expense_date is None:
            return jsonify({"error": "Nieprawidłowy format daty. Użyj RRRR-MM-DD."}), 400

        expense = Expense(
            user_id=user["user_id"],
            title=title,
            amount=amount,
            category=category,
            expense_date=expense_date,
            description=description,
        )

        db.session.add(expense)
        db.session.commit()

        return jsonify(expense_to_dict(expense)), 201

    @app.put("/expenses/<int:expense_id>")
    def update_expense(expense_id):
        user, error = validate_token()
        if error:
            return error

        expense = Expense.query.filter_by(
            id=expense_id,
            user_id=user["user_id"],
        ).first()

        if not expense:
            return jsonify({"error": "Nie znaleziono wydatku."}), 404

        data = request.get_json(silent=True) or {}

        if "title" in data:
            title = (data.get("title") or "").strip()
            if not title:
                return jsonify({"error": "Nazwa wydatku nie może być pusta."}), 400
            expense.title = title

        if "amount" in data:
            amount = parse_amount(data.get("amount"))
            if amount is None:
                return jsonify({"error": "Kwota musi być dodatnią liczbą."}), 400
            expense.amount = amount

        if "category" in data:
            expense.category = (data.get("category") or "").strip() or None

        if "expense_date" in data:
            expense_date = parse_date(data.get("expense_date"))
            if data.get("expense_date") and expense_date is None:
                return jsonify({"error": "Nieprawidłowy format daty. Użyj RRRR-MM-DD."}), 400
            expense.expense_date = expense_date

        if "description" in data:
            expense.description = (data.get("description") or "").strip() or None

        db.session.commit()

        return jsonify(expense_to_dict(expense))

    @app.delete("/expenses/<int:expense_id>")
    def delete_expense(expense_id):
        user, error = validate_token()
        if error:
            return error

        expense = Expense.query.filter_by(
            id=expense_id,
            user_id=user["user_id"],
        ).first()

        if not expense:
            return jsonify({"error": "Nie znaleziono wydatku."}), 404

        db.session.delete(expense)
        db.session.commit()

        return jsonify({"message": "Wydatek został usunięty."})

    @app.get("/expenses/summary")
    def summary():
        user, error = validate_token()
        if error:
            return error

        expenses = Expense.query.filter_by(user_id=user["user_id"]).all()
        total = sum(Decimal(expense.amount) for expense in expenses)

        return jsonify({
            "count": len(expenses),
            "total": float(total),
        })


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
