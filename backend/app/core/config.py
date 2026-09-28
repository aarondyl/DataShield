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

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
