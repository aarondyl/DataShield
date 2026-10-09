from alembic import context
from sqlalchemy import engine_from_config, pool

from identity_service.base import IdentityBase
from identity_service import models  # noqa: F401
from identity_service.settings import IdentitySettings


config = context.config
identity_settings = IdentitySettings.load()
config.set_main_option("sqlalchemy.url", identity_settings.database_url.replace("%", "%%"))
target_metadata = IdentityBase.metadata


def run_migrations_offline():
    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata,
                      literal_binds=True, dialect_opts={"paramstyle": "named"},
                      version_table="alembic_version_identity")
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(config.get_section(config.config_ini_section, {}),
                                     prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata,
                          version_table="alembic_version_identity")
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
