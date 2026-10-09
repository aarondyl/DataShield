"""Cloud API boundary tests: public bundles are read-only and versioned."""
from fastapi.testclient import TestClient


def _client(monkeypatch, token: str = "operator-test-token") -> TestClient:
    monkeypatch.setenv("RUNTIME_MODE", "cloud")
    monkeypatch.setenv("CLOUD_ADMIN_TOKEN", token)
    from app.core.config import get_settings
    get_settings.cache_clear()
    from app.db.base import Base
    from app.db.session import engine
    from app import models  # noqa: F401 - register the RegIntel models
    Base.metadata.create_all(engine)
    from app.main import create_app
    return TestClient(create_app())


def test_cloud_contract_advertises_version_and_rejects_incompatible_major(monkeypatch):
    client = _client(monkeypatch)
    assert client.get("/api/v1/sync/events").headers["X-DataShield-Api-Version"] == "1.0"
    assert client.get("/api/v1/sync/events", headers={"X-DataShield-Api-Version": "2.0"}).status_code == 426


def test_source_ingestion_requires_operator_token(monkeypatch):
    client = _client(monkeypatch)
    assert client.post("/api/v1/sources/1/ingest").status_code == 401
    # The authorization gate runs before the database lookup, proving the
    # endpoint cannot be used anonymously as an outbound-fetch primitive.
    assert client.post("/api/v1/sources/999999/ingest", headers={"Authorization": "Bearer operator-test-token"}).status_code == 404


def test_cloud_does_not_mount_private_tenant_routes(monkeypatch):
    client = _client(monkeypatch)
    assert client.get("/api/companies").status_code == 404
    assert client.get("/api/v1/today?tenant_id=1&product_id=1").status_code == 404


def test_cloud_startup_registers_official_sources_without_claiming_review(monkeypatch):
    client = _client(monkeypatch)
    sources = client.get("/api/v1/sources").json()
    assert {source["source_name"] for source in sources} >= {"PIPL", "DSL", "GDPR"}
    # The public regulation bundle lists ingested versions only. Catalog entries
    # must not be presented as usable law before the official text is parsed.
    assert client.get("/api/v1/regulations").json() == []
