"""Application settings loaded from environment variables or a local .env file."""

from functools import lru_cache
import os

from pydantic_settings import BaseSettings, SettingsConfigDict


_DEFAULT_DATABASE_URL = (
    "sqlite:////tmp/datashield.db" if os.getenv("VERCEL") else "sqlite:///./datashield.db"
)


class Settings(BaseSettings):
    app_name: str = "DataShield API"
    database_url: str = _DEFAULT_DATABASE_URL
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_model: str = "deepseek-chat"
    llm_provider: str = "mock"
    embedding_provider: str = "local"
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 384
    retrieval_top_k: int = 5
    run_seed: bool = True
    # 全局法规智能层定时轮询（MVP 可选，默认关闭）
    scheduler_enabled: bool = False
    scheduler_interval_hours: int = 24
    evaluation_session_days: int = 7
    application_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    legacy_tenant_api_enabled: bool = False
    evaluation_auth_bypass: bool = False
    # 桌面（Electron 内嵌后端）模式：放宽 Origin 校验、禁用 secure cookie
    desktop_mode: bool = False
    mailer_provider: str = "console"
    auth_require_email_verify: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
