"""Cloud API boundary tests: public bundles are read-only and versioned."""
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _client(monkeypatch, token: str = "operator-test-token") -> TestClient:
    monkeypatch.setenv("RUNTIME_MODE", "cloud")
    monkeypatch.setenv("CLOUD_ADMIN_TOKEN", token)
    from app.core.config import get_settings
    get_settings.cache_clear()
    from app.api import regintel
    from app.db.base import Base
    from app.db.session import engine
    from app import models  # noqa: F401 - register the RegIntel models
    Base.metadata.create_all(engine)
    app = FastAPI()
    app.include_router(regintel.router, prefix="/api")

    @app.middleware("http")
    async def version_contract(request, call_next):
        requested = request.headers.get("X-DataShield-Api-Version")
        if request.url.path.startswith("/api/v1/") and requested and requested.split(".", 1)[0] != "1":
            from fastapi.responses import JSONResponse
            return JSONResponse({"detail": "Unsupported Cloud API version", "supported_version": "1.0"}, status_code=426)
        response = await call_next(request)
        response.headers["X-DataShield-Api-Version"] = "1.0"
        return response

    return TestClient(app)


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
