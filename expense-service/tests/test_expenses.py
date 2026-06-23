import pytest

import app as expense_module
from app import create_app, db


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(
        expense_module,
        "validate_token",
        lambda: ({"user_id": "1", "username": "student"}, None),
    )

    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    })

    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


def test_create_and_list_expense(client):
    create_response = client.post("/expenses", json={
        "title": "Bilet miesięczny",
        "amount": "120.00",
        "category": "Transport",
        "expense_date": "2026-06-23",
        "description": "Komunikacja miejska",
    })

    assert create_response.status_code == 201
    assert create_response.get_json()["title"] == "Bilet miesięczny"

    list_response = client.get("/expenses")

    assert list_response.status_code == 200
    data = list_response.get_json()
    assert len(data) == 1
    assert data[0]["amount"] == 120.0


def test_update_expense(client):
    create_response = client.post("/expenses", json={
        "title": "Kawa",
        "amount": "12.00",
    })

    expense_id = create_response.get_json()["id"]

    update_response = client.put(f"/expenses/{expense_id}", json={
        "title": "Kawa i ciastko",
        "amount": "22.50",
    })

    assert update_response.status_code == 200
    data = update_response.get_json()
    assert data["title"] == "Kawa i ciastko"
    assert data["amount"] == 22.5


def test_delete_expense(client):
    create_response = client.post("/expenses", json={
        "title": "Zakupy",
        "amount": "80.00",
    })

    expense_id = create_response.get_json()["id"]

    delete_response = client.delete(f"/expenses/{expense_id}")
    assert delete_response.status_code == 200

    list_response = client.get("/expenses")
    assert list_response.get_json() == []


def test_summary(client):
    client.post("/expenses", json={"title": "A", "amount": "10.00"})
    client.post("/expenses", json={"title": "B", "amount": "20.50"})

    response = client.get("/expenses/summary")

    assert response.status_code == 200
    data = response.get_json()
    assert data["count"] == 2
    assert data["total"] == 30.5
