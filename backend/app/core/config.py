"""Application settings loaded from environment variables or a local .env file."""

from functools import lru_cache
import os
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


_DEFAULT_DATABASE_URL = (
    "sqlite:////tmp/datashield.db" if os.getenv("VERCEL") else "sqlite:///./datashield.db"
)


def default_local_data_dir() -> str:
    """返回本地模式唯一可写根目录，不依赖安装目录或当前目录。"""
    if os.name == "nt":
        base = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys_platform := os.getenv("XDG_DATA_HOME"):
        base = Path(sys_platform)
    else:
        base = Path.home() / ".local" / "share"
    return str(base / "DataShield")


class Settings(BaseSettings):
    runtime_mode: Literal["web", "cloud", "local"] = "web"
    local_data_dir: str = ""
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
    runtime_token: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    def model_post_init(self, __context) -> None:
        if self.runtime_mode == "local":
            self.local_data_dir = self.local_data_dir or default_local_data_dir()
            if "DATABASE_URL" not in os.environ:
                self.database_url = f"sqlite:///{(Path(self.local_data_dir) / 'datashield.db').as_posix()}"
            self.llm_provider = "mock"
            self.embedding_provider = "local"
            self.scheduler_enabled = False

    @property
    def local_regulation_cache_path(self) -> Path:
        return Path(self.local_data_dir) / "regulations" / "cache.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()
