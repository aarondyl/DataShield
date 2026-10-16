from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api import tenant_agent
from app.core.evaluation_auth import CurrentPrincipal
from app.core import llm
from app.tenant.agent.schemas import TenantAnalyzeRequest


def test_desktop_analysis_refuses_mock_provider(monkeypatch):
    desktop_settings = lambda: SimpleNamespace(
        runtime_mode="local", desktop_mode=True, desktop_ai_mode="mock"
    )
    monkeypatch.setattr(tenant_agent, "get_settings", desktop_settings)
    monkeypatch.setattr(llm, "get_settings", desktop_settings)
    monkeypatch.setattr(tenant_agent, "require_company_access", lambda *_: None)
    monkeypatch.setattr(tenant_agent, "require_product_access", lambda *_: None)

    with pytest.raises(HTTPException) as error:
        tenant_agent.analyze(
            TenantAnalyzeRequest(tenant_id=1, product_id=1, trigger_type="MANUAL_SCAN"),
            db=object(),
            principal=CurrentPrincipal(0, "test", 1, "developer"),
        )

    assert error.value.status_code == 409
    assert "真实合规分析" in error.value.detail

    llm.get_llm_client.cache_clear()
    with pytest.raises(llm.LLMError, match="不会使用 Mock"):
        llm.get_llm_client()
    llm.get_llm_client.cache_clear()
