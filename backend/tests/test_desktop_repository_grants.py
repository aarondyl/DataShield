import pytest
from app.core.config import get_settings
from app.local_repositories import grant
from app.understanding.repository import analyze_repository, validate_root
from app.understanding.schemas import RepositoryRequest


def test_local_scan_requires_explicit_process_grant_and_excludes_sensitive_files(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNTIME_MODE", "local")
    monkeypatch.setenv("LOCAL_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("UNDERSTANDING_REPOSITORY_ROOTS", str(tmp_path))
    get_settings.cache_clear()
    root = tmp_path / "repo"
    root.mkdir()
    (root / "README.md").write_text("Product supports user accounts and file uploads.")
    (root / ".env").write_text("API_KEY=private")
    request = RepositoryRequest(repository_path=str(root), analysis_mode="FULL")
    try:
        with pytest.raises(ValueError): validate_root(request)
        grant(str(root))
        assert validate_root(request) == root
        result = analyze_repository(request)
        assert result.files_scanned == 1
        assert all(e.file != ".env" for e in result.evidence)
        unselected = tmp_path / "other"
        unselected.mkdir()
        with pytest.raises(ValueError): validate_root(RepositoryRequest(repository_path=str(unselected), analysis_mode="FULL"))
    finally:
        get_settings.cache_clear()


def test_native_grant_rejects_linked_or_sensitive_paths(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    link = tmp_path / "linked"
    link.symlink_to(root, target_is_directory=True)
    with pytest.raises(ValueError): grant(str(link))
    sensitive = tmp_path / ".ssh"
    sensitive.mkdir()
    with pytest.raises(ValueError): grant(str(sensitive))
