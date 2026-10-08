import pytest
from fastapi import HTTPException
from app.api import local_regulations as api
from app.core.config import Settings
from app.local_regulations.cache import LocalRegulationCache
from app.local_regulations.client import CloudSyncClient

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
