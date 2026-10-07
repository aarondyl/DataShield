"""桌面模式运行时 token 校验（X-Runtime-Token）的中间件行为测试。"""
import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app

TOKEN = "test-runtime-token-0123456789abcdef"


@pytest.fixture
def desktop_mode_with_token(monkeypatch):
    monkeypatch.setenv("DESKTOP_MODE", "true")
    monkeypatch.setenv("DATASHIELD_RUNTIME_TOKEN", TOKEN)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def desktop_mode_without_token(monkeypatch):
    monkeypatch.setenv("DESKTOP_MODE", "true")
    monkeypatch.delenv("DATASHIELD_RUNTIME_TOKEN", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def browser_mode_with_token(monkeypatch):
    monkeypatch.setenv("DESKTOP_MODE", "false")
    monkeypatch.setenv("DATASHIELD_RUNTIME_TOKEN", TOKEN)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_api_request_without_token_is_rejected(desktop_mode_with_token):
    with TestClient(app) as client:
        response = client.get("/api/regulations")
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid runtime token"


def test_api_request_with_wrong_token_is_rejected(desktop_mode_with_token):
    with TestClient(app) as client:
        response = client.get("/api/regulations", headers={"X-Runtime-Token": "wrong-token"})
        assert response.status_code == 401


def test_api_request_with_correct_token_passes(desktop_mode_with_token):
    with TestClient(app) as client:
        response = client.get("/api/regulations", headers={"X-Runtime-Token": TOKEN})
        assert response.status_code == 200


def test_health_check_is_exempt_from_token(desktop_mode_with_token):
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200


def test_token_not_enforced_when_env_missing(desktop_mode_without_token):
    # 未注入 token（如开发模式直接起后端）时不启用校验，避免把自己锁死
    with TestClient(app) as client:
        assert client.get("/api/regulations").status_code == 200


def test_token_not_enforced_outside_desktop_mode(browser_mode_with_token):
    with TestClient(app) as client:
        assert client.get("/api/regulations").status_code == 200
