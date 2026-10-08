"""数据库引擎与会话工厂。

根据 DATABASE_URL 自动切换两种后端：
- ``postgresql+psycopg://...``：PostgreSQL + pgvector（生产/Docker 部署）；
- ``sqlite:///...``：SQLite（本机无 Docker 时的降级开发路径，向量检索自动切换为本地内存实现）。
"""

from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_settings = get_settings()


def _sqlalchemy_url(url: str) -> str:
    """Make provider-style Postgres URLs use the installed psycopg 3 driver."""
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url

#: 当前是否为 SQLite 降级模式（向量存储、启动流程等据此分支）
IS_SQLITE: bool = _settings.database_url.startswith("sqlite")

# SQLite 默认不允许跨线程使用连接，FastAPI 多线程环境下需关闭该检查
_connect_args = {"check_same_thread": False} if IS_SQLITE else {}

engine = create_engine(
    _sqlalchemy_url(_settings.database_url),
    connect_args=_connect_args,
    pool_pre_ping=True,
)

#: 全局会话工厂。expire_on_commit=False 便于提交后继续读取对象属性
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def is_sqlite() -> bool:
    """返回当前是否运行在 SQLite 降级模式。"""
    return IS_SQLITE


def db_kind() -> str:
    """返回数据库种类标识（供健康检查接口展示）。"""
    return "sqlite" if IS_SQLITE else "postgresql"


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖注入用的会话生成器。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """建表（checkfirst，幂等）。

    本机 SQLite 开发路径直接靠它建表；Docker/PostgreSQL 路径由
    ``alembic upgrade head`` 建表，这里作为兜底也不会重复创建。
    """
    from app import models  # noqa: F401  确保全部模型注册到 Base.metadata
    from app.db.base import Base

    # Neon supports pgvector, but the extension must exist before SQLAlchemy can
    # create columns with the ``vector`` type. This is safe on every cold start.
    if not IS_SQLITE:
        with engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    Base.metadata.create_all(bind=engine)
    # Existing Vercel databases may have the pre-Alembic understanding job table.
    # Migration 0005 owns the schema; retain the established startup compatibility
    # path for deployments that start the ASGI app without invoking Alembic.
    if "product_understanding_jobs" in inspect(engine).get_table_names():
        job_columns = {column["name"] for column in inspect(engine).get_columns("product_understanding_jobs")}
        if "product_id" not in job_columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE product_understanding_jobs ADD COLUMN product_id INTEGER"))
    # Vercel starts the ASGI app directly (without an Alembic command). Keep
    # additive profile fields compatible with databases created by older builds.
    product_columns = {column["name"] for column in inspect(engine).get_columns("products")}
    additions = {
        "uses_third_party_sdk": "BOOLEAN DEFAULT FALSE",
        "third_party_sdks": "JSON",
        "privacy_policy_text": "TEXT",
    }
    with engine.begin() as connection:
        for name, sql_type in additions.items():
            if name not in product_columns:
                connection.execute(text(f"ALTER TABLE products ADD COLUMN {name} {sql_type}"))
        connection.execute(text("UPDATE products SET uses_third_party_sdk = FALSE WHERE uses_third_party_sdk IS NULL"))
        connection.execute(text("UPDATE products SET third_party_sdks = '[]' WHERE third_party_sdks IS NULL"))
        connection.execute(text("UPDATE products SET privacy_policy_text = '' WHERE privacy_policy_text IS NULL"))
        # 全局法规智能层：regulations 扩展列兼容旧库
        regulation_columns = {column["name"] for column in inspect(engine).get_columns("regulations")}
        regulation_additions = {
            "official_identifier": "VARCHAR(200) DEFAULT ''",
            "title": "VARCHAR(500) DEFAULT ''",
            "short_name": "VARCHAR(100) DEFAULT ''",
            "authority": "VARCHAR(200) DEFAULT ''",
            "document_type": "VARCHAR(50) DEFAULT ''",
            "status": "VARCHAR(20) DEFAULT 'in_force'",
            "original_language": "VARCHAR(20) DEFAULT ''",
            "canonical_source_url": "VARCHAR(500) DEFAULT ''",
            "current_version_id": "INTEGER",
        }
        for name, sql_type in regulation_additions.items():
            if name not in regulation_columns:
                connection.execute(text(f"ALTER TABLE regulations ADD COLUMN {name} {sql_type}"))


def init_regintel_db() -> None:
    """只初始化云端法规服务所需表，绝不创建租户私有领域表。"""
    from app.db.base import Base
    from app.models import LegalChunk, LegalUnit, Regulation, RegulationArticle, RegulationChange, RegulationEvent, RegulationVersion, RegulatorySource, Requirement
    from app.models.regulatory_source import IngestionRun, SourceSnapshot
    tables = [
        Regulation.__table__, RegulationArticle.__table__, RegulationVersion.__table__, LegalUnit.__table__,
        Requirement.__table__, LegalChunk.__table__, RegulationChange.__table__, RegulationEvent.__table__,
        RegulatorySource.__table__, SourceSnapshot.__table__, IngestionRun.__table__,
    ]
    if not IS_SQLITE:
        with engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=engine, tables=tables)
