from alembic.config import Config

from app.db.alembic_config import set_alembic_database_url


def test_cloud_alembic_url_preserves_percent_encoded_password_characters():
    database_url = "postgresql+psycopg://cloud_user:p%40ss%25word@db.example:5432/legal"
    config = Config()

    set_alembic_database_url(config, database_url)

    assert config.get_main_option("sqlalchemy.url") == database_url
