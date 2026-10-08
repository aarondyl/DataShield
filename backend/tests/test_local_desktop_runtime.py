import json


def test_local_runtime_descriptor_is_user_local_and_contains_loopback_credentials(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNTIME_MODE", "local")
    monkeypatch.setenv("LOCAL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("RUNTIME_TOKEN", "desktop-test-token")
    from app.core.config import get_settings
    get_settings.cache_clear()
    try:
        from app.entrypoints import local
        path = local.write_runtime_descriptor()
        assert path == tmp_path / "runtime.json"
        assert json.loads(path.read_text()) == {
            "base_url": "http://127.0.0.1:18321", "runtime_token": "desktop-test-token", "pid": __import__("os").getpid(),
        }
    finally:
        get_settings.cache_clear()
