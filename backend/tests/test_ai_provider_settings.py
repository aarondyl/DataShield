from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api import ai_provider
from app.core.llm import LLMError, get_llm_client


def test_byok_requires_explicit_data_sharing_consent(monkeypatch, tmp_path):
    from app.core.config import Settings

    settings = Settings(
        runtime_mode="local",
        local_data_dir=str(tmp_path),
        desktop_ai_mode="byok",
        llm_api_key="test-only-key",
        llm_cloud_consent=False,
    )
    monkeypatch.setattr("app.core.llm.get_settings", lambda: settings)
    get_llm_client.cache_clear()
    try:
        with pytest.raises(LLMError, match="发送给你选择的模型服务商"):
            get_llm_client()
    finally:
        get_llm_client.cache_clear()


def test_byok_uses_real_openai_compatible_client_and_provider_identity(monkeypatch, tmp_path):
    from types import SimpleNamespace
    import openai
    from app.core.config import Settings

    calls = {}

    class FakeOpenAI:
        def __init__(self, *, api_key, base_url):
            calls["api_key"] = api_key
            calls["base_url"] = base_url
            self.chat = SimpleNamespace(completions=self)

        def create(self, **kwargs):
            calls["request"] = kwargs
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok":true}'))])

    settings = Settings(
        runtime_mode="local", local_data_dir=str(tmp_path), desktop_ai_mode="byok",
        llm_api_key="test-only-key", llm_base_url="https://api.deepseek.com",
        llm_model="deepseek-flash", llm_cloud_consent=True,
    )
    monkeypatch.setattr("app.core.llm.get_settings", lambda: settings)
    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)
    get_llm_client.cache_clear()
    try:
        client = get_llm_client()
        assert client.provider_name == "byok"
        assert client.chat_json("system", "non-sensitive provider check") == {"ok": True}
        assert calls["api_key"] == "test-only-key"
        assert calls["base_url"] == "https://api.deepseek.com"
        assert calls["request"]["response_format"] == {"type": "json_object"}
    finally:
        get_llm_client.cache_clear()


def test_cloud_gateway_requires_consent_session_and_returns_validated_result(monkeypatch, tmp_path):
    from app.core.cloud_ai import current_cloud_identity_token
    from app.core.config import Settings
    import httpx

    settings = Settings(runtime_mode="local", local_data_dir=str(tmp_path), desktop_ai_mode="cloud",
                        llm_base_url="https://api.datashield.test/identity", llm_model="deepseek-flash",
                        llm_cloud_consent=False)
    monkeypatch.setattr("app.core.llm.get_settings", lambda: settings)
    get_llm_client.cache_clear()
    try:
        with pytest.raises(LLMError, match="同意"):
            get_llm_client()
        settings.llm_cloud_consent = True
        client = get_llm_client()
        with pytest.raises(LLMError, match="登录会话"):
            client.chat_json("system", "input")
        calls = {}

        class Response:
            def raise_for_status(self): pass
            def json(self): return {"result": {"ok": True}, "model": "deepseek-flash"}

        def post(url, **kwargs):
            calls.update(url=url, **kwargs)
            return Response()

        monkeypatch.setattr(httpx, "post", post)
        context = current_cloud_identity_token.set("short-lived-test-token")
        try:
            assert client.chat_json("system", "private product facts") == {"ok": True}
        finally:
            current_cloud_identity_token.reset(context)
        assert calls["url"] == "https://api.datashield.test/identity/v1/ai/chat-json"
        assert calls["headers"]["Authorization"] == "Bearer short-lived-test-token"
        assert calls["json"]["user_prompt"] == "private product facts"
    finally:
        get_llm_client.cache_clear()


def test_ollama_discovery_uses_configured_local_endpoint(monkeypatch, tmp_path):
    from app.core.config import Settings

    settings = Settings(
        runtime_mode="local",
        local_data_dir=str(tmp_path),
        desktop_ai_mode="local",
        llm_base_url="http://127.0.0.1:11434/v1",
        llm_model="qwen2.5:7b",
    )
    monkeypatch.setattr(ai_provider, "_require_local_runtime", lambda: None)
    monkeypatch.setattr(ai_provider, "get_settings", lambda: settings)
    monkeypatch.setattr(ai_provider.httpx, "get", lambda url, timeout: SimpleNamespace(
        raise_for_status=lambda: None,
        json=lambda: {"models": [{"name": "qwen2.5:7b"}, {"name": "llama3.2:3b"}]},
    ))
    assert ai_provider.ollama_models() == {"models": ["qwen2.5:7b", "llama3.2:3b"]}


def test_ollama_discovery_fails_clearly_when_service_is_down(monkeypatch, tmp_path):
    from app.core.config import Settings

    settings = Settings(runtime_mode="local", local_data_dir=str(tmp_path), desktop_ai_mode="local")
    monkeypatch.setattr(ai_provider, "_require_local_runtime", lambda: None)
    monkeypatch.setattr(ai_provider, "get_settings", lambda: settings)
    monkeypatch.setattr(ai_provider.httpx, "get", lambda *args, **kwargs: (_ for _ in ()).throw(TimeoutError()))
    with pytest.raises(HTTPException) as exc:
        ai_provider.ollama_models()
    assert exc.value.status_code == 503
