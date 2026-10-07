from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import SessionLocal
from app.main import app
from app.models import EvaluationSession


def _start(client: TestClient, company_name: str = "Isolated workspace"):
    return client.post(
        "/api/v1/evaluation/start",
        headers={"Origin": "http://localhost:5173"},
        json={
            "name": "Demo User",
            "email": "demo@example.com",
            "company_name": company_name,
            "edition": "developer",
        },
    )


def test_start_uses_opaque_httponly_cookie_and_hashes_token():
    with TestClient(app) as client:
        response = _start(client)
        assert response.status_code == 201
        cookie = response.cookies.get("datashield_evaluation")
        assert cookie and len(cookie) >= 48
        assert "HttpOnly" in response.headers["set-cookie"]
        assert "SameSite=lax" in response.headers["set-cookie"]
        with SessionLocal() as db:
            row = db.scalar(select(EvaluationSession).order_by(EvaluationSession.id.desc()))
            assert row is not None
            assert row.token_hash != cookie
            assert len(row.token_hash) == 64


def test_session_is_required_and_origin_is_validated():
    with TestClient(app) as client:
        assert client.get("/api/v1/evaluation/me").status_code == 401
        rejected = client.post(
            "/api/v1/evaluation/start",
            headers={"Origin": "https://untrusted.example"},
            json={"name": "A", "email": "a@example.com", "company_name": "A"},
        )
        assert rejected.status_code == 403


def test_expired_and_revoked_sessions_are_rejected():
    with TestClient(app) as client:
        assert _start(client).status_code == 201
        with SessionLocal() as db:
            row = db.scalar(select(EvaluationSession).order_by(EvaluationSession.id.desc()))
            row.expires_at = datetime.utcnow() - timedelta(seconds=1)
            db.commit()
        assert client.get("/api/v1/evaluation/me").status_code == 401

        assert _start(client, "Second workspace").status_code == 201
        response = client.post(
            "/api/v1/evaluation/signout",
            headers={"Origin": "http://localhost:5173"},
        )
        assert response.status_code == 200
        assert client.get("/api/v1/evaluation/me").status_code == 401


def test_product_owner_is_always_current_principal():
    with TestClient(app) as client:
        started = _start(client)
        company_id = started.json()["company_id"]
        response = client.post(
            "/api/v1/evaluation/products",
            headers={"Origin": "http://localhost:5173"},
            json={"name": "Demo", "description": "A product", "markets": ["EU"]},
        )
        assert response.status_code == 201
        assert response.json()["company_id"] == company_id
