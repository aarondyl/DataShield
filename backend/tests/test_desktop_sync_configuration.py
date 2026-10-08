import pytest
from fastapi import HTTPException
from app.api import local_regulations as api
from app.core.config import Settings
from app.local_regulations.cache import LocalRegulationCache
from app.local_regulations.client import CloudSyncClient
from app.local_regulations.client import SecureCloudRedirectHandler
from urllib.request import Request
from urllib.error import URLError


def test_cloud_https_sync_rejects_redirect_downgrade_before_request():
    handler = SecureCloudRedirectHandler()
    request = Request("https://regintel.example.org/api/v1/sync/events")
    with pytest.raises(URLError, match="downgrade HTTPS"):
        handler.redirect_request(request, None, 302, "Found", {}, "http://regintel.example.org/api/v1/sync/events")
    redirect = handler.redirect_request(request, None, 302, "Found", {}, "https://regintel.example.org/public/events")
    assert redirect.full_url == "https://regintel.example.org/public/events"

def test_public_endpoint_persists_without_credentials(tmp_path, monkeypatch):
    settings = Settings(runtime_mode="local", local_data_dir=str(tmp_path))
    monkeypatch.setattr(api, "get_settings", lambda: settings)
    assert api.configure(api.EndpointConfiguration(base_url="https://regintel.example.org/"))["base_url"] == "https://regintel.example.org"
    assert Settings(runtime_mode="local", local_data_dir=str(tmp_path)).cloud_regintel_base_url == "https://regintel.example.org"
    for value in ("http://localhost", "https://user:key@example.org", "https://example.org?token=secret"):
        with pytest.raises(HTTPException): api.configure(api.EndpointConfiguration(base_url=value))

def test_unconfigured_sync_marks_offline(tmp_path, monkeypatch):
    settings = Settings(runtime_mode="local", local_data_dir=str(tmp_path))
    monkeypatch.setattr(api, "get_settings", lambda: settings)
    with pytest.raises(HTTPException): api.sync(None)
    assert api.status(None)["using_local_cache"] is True

def test_bundle_fetch_failure_preserves_cache_and_marks_offline(tmp_path, monkeypatch):
    cache = LocalRegulationCache(tmp_path / "regulations.db")
    client = CloudSyncClient("https://example.org", cache)
    def fetch(path, params):
        if path.endswith('/events'): return {"events": [{"event_id": "e1"}]}
        raise ConnectionError('Unavailable bundle')
    monkeypatch.setattr(client, "get_json", fetch)
    with pytest.raises(ConnectionError): client.sync()
    assert cache.progress("all:jurisdiction=*") == (0, 0, 1)


@pytest.mark.parametrize("mode", ["web", "cloud"])
def test_desktop_configuration_and_folder_grants_not_mounted_elsewhere(mode, monkeypatch):
    from app.core.config import get_settings
    from app.main import create_app
    from fastapi.testclient import TestClient
    monkeypatch.setenv("RUNTIME_MODE", mode)
    get_settings.cache_clear()
    try:
        client = TestClient(create_app())
        assert client.get("/api/v1/local-regulations/configuration").status_code == 404
        assert client.post("/api/v1/local-repositories/grant", json={"path": "/tmp"}).status_code == 404
    finally:
        get_settings.cache_clear()
