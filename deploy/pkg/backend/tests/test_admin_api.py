"""Admin API (/api/v1/admin): key guard, user management, reseed and demo reset."""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app

ORIGIN = {"Origin": "http://localhost:5173"}
ADMIN_KEY = "test-admin-key"
ADMIN_HEADERS = {"X-Admin-Key": ADMIN_KEY}


@pytest.fixture(autouse=True)
def enforce_auth(monkeypatch):
    monkeypatch.setenv("EVALUATION_AUTH_BYPASS", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def admin_key(monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", ADMIN_KEY)
    get_settings.cache_clear()
    yield ADMIN_KEY
    get_settings.cache_clear()


def _register(client: TestClient, email: str | None = None, password: str = "Sup3rSecret!"):
    return client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={
            "email": email or f"admin-{uuid.uuid4().hex[:8]}@example.com",
            "password": password,
            "name": "Admin Test User",
            "company_name": "Admin Test Co",
            "edition": "developer",
        },
    )


def _login(client: TestClient, email: str, password: str):
    return client.post("/api/v1/auth/login", headers=ORIGIN, json={"email": email, "password": password})


def test_admin_not_configured_returns_503():
    with TestClient(app) as client:
        response = client.get("/api/v1/admin/overview", headers={"X-Admin-Key": "whatever"})
        assert response.status_code == 503
        assert response.json() == {"detail": "Admin API is not configured"}


def test_admin_wrong_key_returns_401(admin_key):
    with TestClient(app) as client:
        assert client.get("/api/v1/admin/overview").status_code == 401
        wrong = client.get("/api/v1/admin/overview", headers={"X-Admin-Key": "wrong-key"})
        assert wrong.status_code == 401
        assert wrong.json() == {"detail": "Invalid admin key"}


def test_overview_counts(admin_key):
    with TestClient(app) as client:
        response = client.get("/api/v1/admin/overview", headers=ADMIN_HEADERS)
        assert response.status_code == 200, response.text
        body = response.json()
        for field in (
            "users", "companies", "products", "analysis_runs", "tenant_agent_runs",
            "findings", "regulations", "legal_units", "active_sessions",
        ):
            assert field in body and isinstance(body[field], int)
        assert body["regulations"] >= 3  # 种子三部法规
        assert body["legal_units"] > 0


def test_disable_blocks_login_and_enable_restores(admin_key):
    with TestClient(app) as client:
        email = f"lock-{uuid.uuid4().hex[:8]}@example.com"
        registered = _register(client, email)
        assert registered.status_code == 201
        user_id = registered.json()["user_id"]
        assert _login(client, email, "Sup3rSecret!").status_code == 200

        disabled = client.post(f"/api/v1/admin/users/{user_id}/disable", headers=ADMIN_HEADERS)
        assert disabled.status_code == 200, disabled.text
        assert disabled.json()["disabled"] is True
        assert disabled.json()["revoked_sessions"] >= 1

        blocked = _login(client, email, "Sup3rSecret!")
        assert blocked.status_code == 403
        assert blocked.json() == {"detail": "Account disabled"}
        # 已有会话同样被拒（require_principal 检查 disabled）
        assert client.get("/api/v1/auth/me").status_code in {401, 403}

        enabled = client.post(f"/api/v1/admin/users/{user_id}/enable", headers=ADMIN_HEADERS)
        assert enabled.status_code == 200
        assert enabled.json()["disabled"] is False
        assert _login(client, email, "Sup3rSecret!").status_code == 200


def test_reset_password_issues_working_password(admin_key):
    with TestClient(app) as client:
        email = f"reset-{uuid.uuid4().hex[:8]}@example.com"
        registered = _register(client, email)
        assert registered.status_code == 201
        user_id = registered.json()["user_id"]
        client.post("/api/v1/auth/logout", headers=ORIGIN)

        reset = client.post(f"/api/v1/admin/users/{user_id}/reset-password", headers=ADMIN_HEADERS)
        assert reset.status_code == 200, reset.text
        new_password = reset.json()["new_password"]
        assert len(new_password) == 10

        assert _login(client, email, "Sup3rSecret!").status_code == 401
        assert _login(client, email, new_password).status_code == 200


def test_users_list_contains_registered_user(admin_key):
    with TestClient(app) as client:
        email = f"list-{uuid.uuid4().hex[:8]}@example.com"
        assert _register(client, email).status_code == 201
        response = client.get("/api/v1/admin/users", headers=ADMIN_HEADERS)
        assert response.status_code == 200
        row = next(u for u in response.json() if u["email"] == email)
        assert row["company_name"] == "Admin Test Co"
        assert row["disabled"] is False
        assert row["active_sessions"] >= 1
        for field in ("id", "display_name", "company_id", "edition", "email_verified", "created_at", "last_login_at"):
            assert field in row


def test_regulations_reseed_restores_seed_state(admin_key):
    with TestClient(app) as client:
        before = client.get("/api/v1/admin/regulations", headers=ADMIN_HEADERS)
        assert before.status_code == 200
        assert len(before.json()) >= 3

        reseed = client.post("/api/v1/admin/regulations/reseed", headers=ADMIN_HEADERS)
        assert reseed.status_code == 200, reseed.text
        stats = reseed.json()
        assert stats["reseeded"] is True
        assert stats["regulations"] == 3
        assert stats["versions"] >= 3
        assert stats["legal_units"] > 0
        assert stats["requirements"] > 0
        assert stats["chunks"] > 0

        after = client.get("/api/v1/admin/regulations", headers=ADMIN_HEADERS)
        names = {r["short_name"] for r in after.json()}
        assert {"GDPR", "PIPL", "DSL"} <= names
        for row in after.json():
            assert row["versions"] >= 1
            assert row["legal_units"] > 0
            assert row["requirements"] > 0


def test_demo_reset_removes_evaluation_workspaces(admin_key):
    with TestClient(app) as client:
        started = client.post(
            "/api/v1/evaluation/start",
            headers=ORIGIN,
            json={"name": "Eval User", "email": f"eval-{uuid.uuid4().hex[:8]}@example.com", "company_name": "Eval Demo Co", "edition": "developer"},
        )
        assert started.status_code == 201
        company_id = started.json()["company_id"]

        companies = client.get("/api/v1/admin/companies", headers=ADMIN_HEADERS)
        assert any(c["id"] == company_id and c["business_model"] == "evaluation" for c in companies.json())

        reset = client.post("/api/v1/admin/demo/reset", headers=ADMIN_HEADERS)
        assert reset.status_code == 200, reset.text
        assert reset.json()["deleted_companies"] >= 1

        after = client.get("/api/v1/admin/companies", headers=ADMIN_HEADERS)
        assert all(c["business_model"] != "evaluation" for c in after.json())
