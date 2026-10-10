"""Cloud 法规数据库独立迁移环境，绝不引用 Web/Local 迁移链。"""
from logging.config import fileConfig
from alembic import context
from sqlalchemy import engine_from_config, pool
from app.db.alembic_config import set_alembic_database_url
from app.core.config import get_settings

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
# Keep URL-encoded credentials intact across Alembic's ConfigParser round-trip.
set_alembic_database_url(config, get_settings().database_url)


def run_migrations_offline():
    context.configure(url=config.get_main_option("sqlalchemy.url"), literal_binds=True,
                      dialect_opts={"paramstyle": "named"}, version_table="alembic_version_cloud")
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, version_table="alembic_version_cloud")
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode(): run_migrations_offline()
else: run_migrations_online()
