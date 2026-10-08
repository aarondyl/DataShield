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
    database_url_file: str = ""
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_model: str = "deepseek-chat"
    llm_provider: str = "mock"
    desktop_ai_mode: Literal["mock", "byok", "local", "cloud"] = "mock"
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
    # Only public regulation events are fetched from this HTTPS endpoint. Local
    # Product Twin, evidence and tenant data are never sent to it.
    cloud_regintel_base_url: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    def model_post_init(self, __context) -> None:
        # 容器部署从 Docker/Kubernetes Secret 文件读取连接串，避免把密码写入
        # Compose 环境、镜像层或命令行日志。显式 DATABASE_URL 仍用于开发和 CI。
        if self.database_url_file:
            self.database_url = Path(self.database_url_file).read_text(encoding="utf-8").strip()
        if self.runtime_mode == "local":
            self.local_data_dir = self.local_data_dir or default_local_data_dir()
            if "DATABASE_URL" not in os.environ:
                self.database_url = f"sqlite:///{(Path(self.local_data_dir) / 'datashield.db').as_posix()}"
            # Desktop 默认保持可重复的离线 mock；只有该显式模式才覆盖 provider。
            # byok/local/cloud 是未来 Desktop 选择边界：本层保留用户 provider
            # 配置，不保存密钥，也不在此实现远程网关或本地模型客户端。
            if self.desktop_ai_mode == "mock":
                self.llm_provider = "mock"
                self.embedding_provider = "local"
            # Desktop 通过主进程持有的短期 runtime token 调用这些业务路由。
            # 这不是 Web 共享预览的匿名开放：所有 /api/*（健康检查除外）仍由
            # enforce_local_runtime_token 验证，且数据只在本机 SQLite。
            self.legacy_tenant_api_enabled = True
            # Desktop 的 renderer 只能经 Rust bridge 调用受限本地 API；因此本机
            # 单用户 workspace 不再要求 Web evaluation cookie。它不是共享预览的
            # 匿名开放，外部进程仍必须持有短期 runtime token。
            self.evaluation_auth_bypass = True
            self.scheduler_enabled = False

    @property
    def local_regulation_cache_path(self) -> Path:
        # 法规缓存与本地业务实体必须位于同一 SQLite 事务边界，保证
        # 同步游标、法规外键和 Finding 溯源不会跨库失配。
        if self.runtime_mode == "local":
            return Path(self.local_data_dir) / "datashield.db"
        return Path(self.local_data_dir) / "regulations" / "cache.db"

    @property
    def local_runtime_descriptor_path(self) -> Path:
        """桌面壳读取的本机运行时描述；只应存在于当前用户应用目录。"""
        return Path(self.local_data_dir) / "runtime.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()
