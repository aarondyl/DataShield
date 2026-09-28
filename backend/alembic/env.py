"""Alembic 运行环境。

数据库地址从应用配置（环境变量 / .env 的 DATABASE_URL）读取，
与运行时保持一致，不在 alembic.ini 里写死连接串。
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

from app.core.config import get_settings
from app.db.base import Base
from app import models  # noqa: F401  确保全部模型注册到 Base.metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 注入应用配置中的数据库地址
config.set_main_option("sqlalchemy.url", get_settings().database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式：只生成 SQL，不连接数据库。"""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：连接数据库执行迁移。"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
