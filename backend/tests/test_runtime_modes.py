from app.core.config import get_settings
from sqlalchemy import create_engine, inspect


def test_local_mode_defaults_to_offline_mock_processing(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNTIME_MODE", "local"); monkeypatch.setenv("LOCAL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LLM_PROVIDER", "api"); monkeypatch.setenv("LLM_API_KEY", "fake")
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert settings.database_url.endswith("datashield.db")
        assert settings.local_regulation_cache_path == tmp_path / "datashield.db"
        assert settings.llm_provider == "mock" and settings.embedding_provider == "local"
        assert settings.legacy_tenant_api_enabled is True
        assert settings.scheduler_enabled is False
    finally: get_settings.cache_clear()


def test_local_byok_mode_preserves_explicit_provider_configuration(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNTIME_MODE", "local"); monkeypatch.setenv("LOCAL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DESKTOP_AI_MODE", "byok"); monkeypatch.setenv("LLM_PROVIDER", "api")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "api")
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert settings.desktop_ai_mode == "byok"
        assert settings.llm_provider == "api" and settings.embedding_provider == "api"
        assert settings.scheduler_enabled is False
    finally: get_settings.cache_clear()


def test_cloud_initialization_creates_only_regintel_tables(tmp_path, monkeypatch):
    import app.db.session as session
    cloud_engine = create_engine(f"sqlite:///{tmp_path / 'cloud.db'}")
    monkeypatch.setattr(session, "engine", cloud_engine)
    monkeypatch.setattr(session, "IS_SQLITE", True)
    session.init_regintel_db()
    names = set(inspect(cloud_engine).get_table_names())
    assert {"regulations", "regulation_versions", "legal_units", "requirements", "legal_chunks", "regulation_events", "regulatory_sources"} <= names
    assert not ({"companies", "products", "product_twin_versions", "findings", "remediations", "feedback"} & names)
    # Existing unrelated data is intentionally preserved, never deleted.
    with cloud_engine.begin() as conn: conn.exec_driver_sql("CREATE TABLE preserved_data (id INTEGER)")
    session.init_regintel_db()
    assert "preserved_data" in inspect(cloud_engine).get_table_names()
