"""Helpers for values stored in Alembic's interpolating ConfigParser."""


def set_alembic_database_url(config, database_url: str) -> None:
    """Store a SQLAlchemy URL without interpreting percent-encoded credentials."""
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
