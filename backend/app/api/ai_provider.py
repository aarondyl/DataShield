"""Local-only provider diagnostics for user-selected model providers."""

from fastapi import APIRouter, HTTPException
import httpx

from app.core.config import get_settings
from app.core.llm import LLMError, get_llm_client

router = APIRouter(prefix="/ai", tags=["local-ai"])


def _require_local_runtime() -> None:
    if get_settings().runtime_mode != "local":
        raise HTTPException(status_code=404, detail="Not found")


@router.post("/provider/test")
def test_provider() -> dict[str, str]:
    """Make a real, non-sensitive inference request to the active provider."""
    _require_local_runtime()
    settings = get_settings()
    if settings.desktop_ai_mode == "mock":
        raise HTTPException(status_code=409, detail="请先选择并保存一个真实 AI 服务商")
    try:
        client = get_llm_client()
        client.chat_json(
            "Return a JSON object with the single boolean property ok set to true.",
            "This is a provider connectivity check. Do not include any user or product data.",
        )
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None
    except Exception:
        raise HTTPException(status_code=502, detail="模型服务连接或响应校验失败") from None
    return {"provider": client.provider_name, "model": client.model_name, "status": "ok"}


@router.get("/provider/ollama-models")
def ollama_models() -> dict[str, list[str]]:
    """List models from the loopback Ollama instance, without cloud traffic."""
    _require_local_runtime()
    try:
        response = httpx.get("http://127.0.0.1:11434/api/tags", timeout=5.0)
        response.raise_for_status()
        payload = response.json()
        models = payload.get("models")
        if not isinstance(models, list):
            raise ValueError("invalid model list")
        return {"models": [item["name"] for item in models if isinstance(item, dict) and isinstance(item.get("name"), str)]}
    except Exception:
        raise HTTPException(status_code=503, detail="无法连接本机 Ollama。请确认 Ollama 正在运行") from None
