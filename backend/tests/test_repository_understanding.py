import json
import os
from pathlib import Path
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from app.api.repository_understanding import router
from app.understanding.jobs import JobStore, get_store
from app.understanding.repository import analyze_repository
from app.understanding.schemas import RepositoryRequest


@pytest.fixture
def repository(tmp_path):
    root = tmp_path / "product"
    root.mkdir()
    (root / "package.json").write_text(json.dumps({"dependencies": {"react": "1", "stripe": "2"},
        "description": "openai is not installed"}))
    (root / "main.py").write_text('from fastapi import FastAPI\ndef delete_account():\n    email = "sample"\nAPI_KEY = "sk-private-value-do-not-return"\n')
    (root / ".env").write_text("OPENAI_API_KEY=secret")
    (root / "node_modules").mkdir()
    (root / "node_modules" / "ignored.py").write_text("import anthropic")
    return root


def run(root, mode="FULL", **kwargs):
    return analyze_repository(RepositoryRequest(repository_path=str(root), analysis_mode=mode, **kwargs), [str(root)])


def test_facts_evidence_and_read_only(repository):
    before = {p: p.read_bytes() for p in repository.rglob("*") if p.is_file()}
    result = run(repository)
    assert {"React", "Python", "FastAPI", "Node.js"} <= set(result.detected_stack)
    assert [v.name for v in result.vendors] == ["Stripe"]
    assert result.capabilities["account_deletion"].status == "PARTIAL"
    assert result.capabilities["cookie_consent"].status == "NOT_DETECTED"
    assert any(e.file == "main.py" and e.line_start == 2 for e in result.evidence)
    assert "sk-private" not in result.model_dump_json()
    assert "Potential secret/configuration detected." in result.limitations
    ids = {e.evidence_id for e in result.evidence}
    assert all(set(f.evidence_ids) <= ids for f in result.features + result.stack_facts + result.vendors)
    assert before == {p: p.read_bytes() for p in before}


def test_modes(repository, monkeypatch):
    metadata = run(repository, "METADATA_ONLY")
    assert "FastAPI" not in metadata.detected_stack
    assert metadata.capabilities["account_deletion"].status == "UNKNOWN"
    selected = run(repository, "SELECTED_PATHS", selected_paths=["package.json"])
    assert selected.files_scanned == 1
    assert "Python" not in selected.detected_stack
    # NO_REPOSITORY must not even check whether a supplied path exists.
    monkeypatch.setattr(Path, "resolve", lambda *a, **k: pytest.fail("filesystem touched"))
    result = analyze_repository(RepositoryRequest(repository_path="/nonexistent", analysis_mode="NO_REPOSITORY",
        product_description="An AI chat product"))
    assert result.files_scanned == 0
    assert result.capabilities["data_export"].status == "UNKNOWN"
    assert next(f for f in result.features if f.name == "AI_chat").status == "PARTIAL"


@pytest.mark.parametrize("selection", ["../", ".env", "node_modules", "missing.py"])
def test_selection_escape(repository, selection):
    with pytest.raises(ValueError):
        run(repository, "SELECTED_PATHS", selected_paths=[selection])


def test_root_allowlist(repository):
    with pytest.raises(ValueError):
        analyze_repository(RepositoryRequest(repository_path=str(repository)), [])


def test_links_and_large_files(repository, tmp_path):
    outside = tmp_path / "outside.py"
    outside.write_text("import openai")
    os.link(outside, repository / "hard.py")
    (repository / "big.py").write_text("x" * 256001)
    result = run(repository)
    assert "OpenAI" not in [v.name for v in result.vendors]
    assert not result.coverage_complete
    assert result.capabilities["data_export"].status == "UNKNOWN"


def test_api_lifecycle(repository, tmp_path, monkeypatch):
    monkeypatch.setenv("UNDERSTANDING_API_KEY", "test-key")
    monkeypatch.setenv("UNDERSTANDING_REPOSITORY_ROOTS", str(repository))
    store = JobStore(create_engine(f"sqlite:///{tmp_path / 'jobs.db'}", connect_args={"check_same_thread": False}))
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_store] = lambda: store
    client = TestClient(app)
    body = {"repository_path": str(repository), "analysis_mode": "FULL"}
    assert client.post("/v1/analyze-repository", json=body).status_code == 401
    headers = {"Authorization": "Bearer test-key"}
    response = client.post("/v1/analyze-repository", json=body, headers=headers)
    assert response.status_code == 202
    assert response.json()["status"] == "PENDING"
    result = client.get("/v1/repository-analysis/" + response.json()["analysis_id"], headers=headers).json()
    assert result["status"] == "COMPLETED"
    assert result["repository_analysis"]["files_scanned"] == 2
    assert client.get("/v1/repository-analysis/missing", headers=headers).status_code == 404
    assert client.post("/v1/analyze-repository", json={"analysis_mode": "SELECTED_PATHS"}, headers=headers).status_code == 422
