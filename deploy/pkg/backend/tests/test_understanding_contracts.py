from fastapi import HTTPException
import pytest
from sqlalchemy import create_engine
from app.understanding.jobs import JobStore
from app.understanding.schemas import Fact, RepoAnalysisResult, WebsiteAnalysisResult, find_conflicts


def test_conflicts_preserve_both_sources():
    repo = RepoAnalysisResult(repository_id="r", analysis_mode="FULL", features=[
        Fact(name="AI_generation", status="NOT_DETECTED", confidence=.5, evidence_ids=["r1"])])
    site = WebsiteAnalysisResult(website_id="s", url="https://example.com", features=[
        Fact(name="AI_generation", confidence=.8, evidence_ids=["s1"])])
    conflict, = find_conflicts(repo, site)
    assert conflict.repo_value.evidence_ids == ["r1"]
    assert conflict.website_value.evidence_ids == ["s1"]
    assert repo.features[0].status == "NOT_DETECTED"
    site.features[0].status = "UNKNOWN"
    assert not find_conflicts(repo, site)


def test_jobs_persist_and_hide_errors(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'jobs.db'}")
    store = JobStore(engine)
    job = store.create("repository", "owner")
    assert job.status == "PENDING"
    def fail():
        assert store.get(job.analysis_id, "repository", "owner").status == "RUNNING"
        raise RuntimeError("secret-value")
    store.run(job, fail)
    restored = JobStore(engine).get(job.analysis_id, "repository", "owner")
    assert restored.status == "FAILED"
    assert "secret-value" not in restored.model_dump_json()
    with pytest.raises(HTTPException):
        store.get(job.analysis_id, "repository", "other")
    with pytest.raises(HTTPException):
        store.get(job.analysis_id, "website", "owner")
