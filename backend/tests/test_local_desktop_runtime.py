import json
import socket


def test_local_runtime_descriptor_is_user_local_and_contains_loopback_credentials(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNTIME_MODE", "local")
    monkeypatch.setenv("LOCAL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("RUNTIME_TOKEN", "desktop-test-token")
    from app.core.config import get_settings
    get_settings.cache_clear()
    try:
        from app.entrypoints import local
        listener = local.allocate_loopback_listener()
        try:
            host, port = listener.getsockname()
            path = local.write_runtime_descriptor(port)
        finally:
            listener.close()
        assert path == tmp_path / "runtime.json"
        assert json.loads(path.read_text()) == {
            "base_url": f"http://127.0.0.1:{port}", "runtime_token": "desktop-test-token", "pid": __import__("os").getpid(),
        }
        assert host == "127.0.0.1" and port != 18321
    finally:
        get_settings.cache_clear()


def test_listener_uses_dynamic_loopback_port():
    from app.entrypoints import local
    first = local.allocate_loopback_listener()
    try:
        listener = local.allocate_loopback_listener()
        try:
            assert listener.getsockname()[0] == "127.0.0.1"
            assert listener.getsockname()[1] != 18321
            assert listener.getsockname()[1] != first.getsockname()[1]
        finally:
            listener.close()
    finally:
        first.close()
