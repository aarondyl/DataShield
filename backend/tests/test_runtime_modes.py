from app.core.config import get_settings
from app.db.base import Base


def test_local_mode_forces_offline_private_processing(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNTIME_MODE", "local"); monkeypatch.setenv("LOCAL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LLM_PROVIDER", "api"); monkeypatch.setenv("LLM_API_KEY", "fake")
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert settings.database_url.endswith("datashield.db")
        assert settings.llm_provider == "mock" and settings.embedding_provider == "local"
        assert settings.scheduler_enabled is False
    finally: get_settings.cache_clear()


def test_cloud_table_selection_excludes_private_tables():
    from app.db.session import init_regintel_db
    # The implementation exposes its table selection through create_all; inspect
    # source to guard against accidental private-table initialization.
    import inspect
    source = inspect.getsource(init_regintel_db)
    for private_table in ("companies", "products", "product_twin", "findings", "remediations", "feedback"):
        assert private_table not in source
