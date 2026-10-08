from app.core.config import get_settings


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
