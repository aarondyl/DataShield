"""Email registration/login API: sessions, cookies and verification flow."""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app

ORIGIN = {"Origin": "http://localhost:5173"}


@pytest.fixture(autouse=True)
def enforce_auth(monkeypatch):
    monkeypatch.setenv("EVALUATION_AUTH_BYPASS", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _register(client: TestClient, email: str | None = None, password: str = "Sup3rSecret!"):
    return client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={
            "email": email or f"user-{uuid.uuid4().hex[:8]}@example.com",
            "password": password,
            "name": "Demo User",
            "company_name": "Demo Co",
            "edition": "developer",
        },
    )


def test_register_returns_201_and_user_payload():
    with TestClient(app) as client:
        response = _register(client)
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["user_id"] and body["company_id"]
        assert body["edition"] == "developer"
        assert body["email_verified"] is False
        assert "HttpOnly" in response.headers["set-cookie"]


def test_duplicate_email_registration_returns_409():
    with TestClient(app) as client:
        email = f"dup-{uuid.uuid4().hex[:8]}@example.com"
        assert _register(client, email).status_code == 201
        again = _register(client, email)
        assert again.status_code == 409
        assert again.json() == {"detail": "Email already registered"}


def test_email_is_normalized_for_registration_and_login():
    with TestClient(app) as client:
        email = f"Mixed-{uuid.uuid4().hex[:8]}@Example.com"
        registered = _register(client, email)
        assert registered.status_code == 201
        assert registered.json()["email"] == email.casefold()
        assert client.post("/api/v1/auth/logout", headers=ORIGIN).status_code == 200
        assert client.post("/api/v1/auth/login", headers=ORIGIN, json={"email": email.lower(), "password": "Sup3rSecret!"}).status_code == 200
        assert _register(client, email.lower()).status_code == 409


def test_login_success_and_wrong_password():
    with TestClient(app) as client:
        email = f"login-{uuid.uuid4().hex[:8]}@example.com"
        registered = _register(client, email)
        assert registered.status_code == 201
        assert client.post("/api/v1/auth/logout", headers=ORIGIN).status_code == 200

        wrong = client.post("/api/v1/auth/login", headers=ORIGIN, json={"email": email, "password": "WrongPass123"})
        assert wrong.status_code == 401
        assert wrong.json() == {"detail": "Invalid email or password"}

        ok = client.post("/api/v1/auth/login", headers=ORIGIN, json={"email": email, "password": "Sup3rSecret!"})
        assert ok.status_code == 200, ok.text
        assert ok.json()["email"] == email
        assert ok.json()["user_id"] == registered.json()["user_id"]


def test_me_returns_registered_user_and_logout_revokes():
    with TestClient(app) as client:
        assert _register(client).status_code == 201
        me = client.get("/api/v1/auth/me")
        assert me.status_code == 200
        assert "user_id" in me.json() and me.json()["edition"] == "developer"

        assert client.post("/api/v1/auth/logout", headers=ORIGIN).status_code == 200
        assert client.get("/api/v1/auth/me").status_code == 401


def test_verify_email_skipped_when_not_required():
    with TestClient(app) as client:
        assert _register(client).status_code == 201
        response = client.post("/api/v1/auth/verify-email", headers=ORIGIN, json={"code": "000000"})
        assert response.status_code == 200
        assert response.json() == {"verified": True, "skipped": True}


def test_registered_cookie_accesses_protected_apis():
    with TestClient(app) as client:
        assert client.get("/api/v1/evaluation/me").status_code == 401
        registered = _register(client)
        assert registered.status_code == 201
        evaluation_me = client.get("/api/v1/evaluation/me")
        assert evaluation_me.status_code == 200
        assert evaluation_me.json()["company_id"] == registered.json()["company_id"]
        assert evaluation_me.json()["edition"] == "developer"


def test_registered_users_are_isolated_to_their_company():
    with TestClient(app) as client_a, TestClient(app) as client_b:
        user_a = _register(client_a)
        user_b = _register(client_b)
        assert user_a.status_code == user_b.status_code == 201
        company_b = user_b.json()["company_id"]
        product_b = client_b.post("/api/v1/evaluation/products", headers=ORIGIN, json={
            "name": "Private product", "description": "Private", "markets": ["EU"],
        })
        assert product_b.status_code == 201
        foreign = client_a.get("/api/v1/today", params={"tenant_id": company_b, "product_id": product_b.json()["id"]})
        assert foreign.status_code == 404
