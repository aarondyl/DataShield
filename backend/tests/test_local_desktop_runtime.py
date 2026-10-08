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


def test_runtime_cleanup_preserves_other_process_descriptor(monkeypatch, tmp_path):
    from app.core.config import Settings
    from app.entrypoints import local
    monkeypatch.setattr(local, "settings", Settings(runtime_mode="local", local_data_dir=str(tmp_path)))
    path = local.write_runtime_descriptor(23456)
    other = json.loads(path.read_text())
    other["pid"] = __import__("os").getpid() + 1
    path.write_text(json.dumps(other))
    local.remove_owned_runtime_descriptor()
    assert path.exists()
    local.write_runtime_descriptor(23456)
    local.remove_owned_runtime_descriptor()
    assert not path.exists()


def test_each_launch_rotates_inherited_token_and_cleans_up(monkeypatch, tmp_path):
    from app.core.config import Settings
    from app.entrypoints import local
    import uvicorn
    monkeypatch.setattr(local, "settings", Settings(runtime_mode="local", local_data_dir=str(tmp_path), runtime_token="inherited"))
    tokens = []
    def run(server, sockets):
        descriptor = json.loads((tmp_path / "runtime.json").read_text())
        tokens.append(descriptor["runtime_token"])
        assert sockets[0].getsockname()[0] == "127.0.0.1"
    monkeypatch.setattr(uvicorn.Server, "run", run)
    monkeypatch.setenv("RUNTIME_TOKEN", "inherited")
    local.run_local()
    assert not (tmp_path / "runtime.json").exists()
    local.run_local()
    assert tokens[0] != tokens[1] and "inherited" not in tokens
