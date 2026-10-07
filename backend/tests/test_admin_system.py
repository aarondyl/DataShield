"""Admin System API (/api/v1/admin/system, /v1/admin/regintel/*): key guard and payloads."""
import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app

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


def test_system_endpoints_require_admin_key():
    with TestClient(app) as client:
        assert client.get("/api/v1/admin/system").status_code in (401, 503)
        assert client.get("/api/v1/admin/regintel/status").status_code in (401, 503)
        assert client.post("/api/v1/admin/regintel/sources/1/ingest").status_code in (401, 503)


def test_system_endpoints_reject_wrong_key(admin_key):
    with TestClient(app) as client:
        assert client.get("/api/v1/admin/system", headers={"X-Admin-Key": "wrong"}).status_code == 401
        assert client.get("/api/v1/admin/regintel/status", headers={"X-Admin-Key": "wrong"}).status_code == 401


def test_system_info_fields(admin_key):
    with TestClient(app) as client:
        response = client.get("/api/v1/admin/system", headers=ADMIN_HEADERS)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["version"] == app.version
        assert body["db_kind"] in {"sqlite", "postgresql"}
        assert body["llm_provider"] == "mock"
        assert body["llm_model"]
        assert body["embedding_provider"] == "local"
        assert isinstance(body["scheduler_enabled"], bool)
        assert isinstance(body["scheduler_interval_hours"], int)
        assert body["uptime_seconds"] >= 0
        assert body["started_at"]
        assert body["python_version"]
        env = body["env"]
        for field in ("desktop_mode", "legacy_tenant_api_enabled", "evaluation_auth_bypass"):
            assert field in env and isinstance(env[field], bool)


def test_regintel_status_fields(admin_key):
    with TestClient(app) as client:
        response = client.get("/api/v1/admin/regintel/status", headers=ADMIN_HEADERS)
        assert response.status_code == 200, response.text
        body = response.json()
        assert len(body["sources"]) >= 3  # 种子三部法规来源
        source = body["sources"][0]
        for field in ("id", "name", "enabled", "last_checked_at", "last_success_at", "last_run_status"):
            assert field in source
        assert isinstance(body["recent_ingestion_runs"], list)
        assert len(body["recent_ingestion_runs"]) <= 10
        run = body["recent_ingestion_runs"][0]
        for field in ("id", "source_id", "status", "started_at", "changes_count"):
            assert field in run
        assert isinstance(body["events_count"], int)
        assert body["scheduler"]["enabled"] is False
        assert body["scheduler"]["interval_hours"] >= 1


def test_ingest_trigger_returns_run(admin_key):
    with TestClient(app) as client:
        status = client.get("/api/v1/admin/regintel/status", headers=ADMIN_HEADERS)
        source_id = status.json()["sources"][0]["id"]
        response = client.post(f"/api/v1/admin/regintel/sources/{source_id}/ingest", headers=ADMIN_HEADERS)
        assert response.status_code == 201, response.text
        body = response.json()
        # 种子来源内容未变化：流水线幂等返回 NO_CHANGE
        assert body["status"] == "NO_CHANGE"
        assert body["source_id"] == source_id
        # 触发后应出现在最近运行列表中
        refreshed = client.get("/api/v1/admin/regintel/status", headers=ADMIN_HEADERS).json()
        assert refreshed["recent_ingestion_runs"][0]["id"] == body["id"]


def test_ingest_unknown_source_returns_404(admin_key):
    with TestClient(app) as client:
        response = client.post("/api/v1/admin/regintel/sources/999999/ingest", headers=ADMIN_HEADERS)
        assert response.status_code == 404
