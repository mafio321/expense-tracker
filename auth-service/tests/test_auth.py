import pytest

from app import create_app, db


@pytest.fixture()
def client():
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "JWT_SECRET_KEY": "test-secret",
    })

    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


def test_register_and_login(client):
    register_response = client.post("/auth/register", json={
        "username": "student",
        "password": "secret123",
    })

    assert register_response.status_code == 201
    assert register_response.get_json()["username"] == "student"

    login_response = client.post("/auth/login", json={
        "username": "student",
        "password": "secret123",
    })

    assert login_response.status_code == 200
    data = login_response.get_json()
    assert "token" in data
    assert data["username"] == "student"


def test_duplicate_username_is_rejected(client):
    payload = {"username": "student", "password": "secret123"}

    first_response = client.post("/auth/register", json=payload)
    second_response = client.post("/auth/register", json=payload)

    assert first_response.status_code == 201
    assert second_response.status_code == 409


def test_invalid_login_is_rejected(client):
    client.post("/auth/register", json={
        "username": "student",
        "password": "secret123",
    })

    response = client.post("/auth/login", json={
        "username": "student",
        "password": "wrong-password",
    })

    assert response.status_code == 401


def test_token_verification(client):
    client.post("/auth/register", json={
        "username": "student",
        "password": "secret123",
    })

    login_response = client.post("/auth/login", json={
        "username": "student",
        "password": "secret123",
    })

    token = login_response.get_json()["token"]

    verify_response = client.post(
        "/auth/verify",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert verify_response.status_code == 200
    assert verify_response.get_json()["valid"] is True
