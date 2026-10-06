"""Product Twin preserves source observations, evidence and user decisions."""

import hashlib
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from app.api import product_twin, repository_understanding, website_understanding
from app.db.base import Base
from app.db.session import get_db
from app.models import Company, Product
from app.understanding.jobs import JobStore, get_store
from app.understanding.schemas import Evidence, Fact, RepoAnalysisResult, WebsiteAnalysisResult


@pytest.fixture
def context(tmp_path, monkeypatch):
    monkeypatch.setenv("UNDERSTANDING_API_KEY", "test-service-key")
    engine = create_engine(f"sqlite:///{tmp_path / 'twin.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([Company(name="Company A"), Company(name="Company B")])
        db.commit()
        db.add_all([Product(company_id=1, name="Product A", collects_health_data=True),
                    Product(company_id=2, name="Product B")])
        db.commit()
    store = JobStore(engine)
    app = FastAPI()
    for router in (repository_understanding.router, website_understanding.router, product_twin.router):
        app.include_router(router)
    def session():
        with Session(engine) as db:
            yield db
    app.dependency_overrides[get_db] = session
    app.dependency_overrides[get_store] = lambda: store
    return TestClient(app), store, engine


def _completed(store, kind, result, product_id=1):
    job = store.create(kind, hashlib.sha256(b"test-service-key").hexdigest(), product_id)
    job.status = "COMPLETED"
    setattr(job, f"{kind}_analysis", result)
    store.save(job)
    return job.analysis_id


def _repo(status="PRESENT"):
    return RepoAnalysisResult(repository_id="r1", analysis_mode="FULL", files_scanned=1, coverage_complete=True,
        features=[Fact(name="login", status=status, confidence=.8, evidence_ids=["ev_0001"])],
        evidence=[Evidence(evidence_id="ev_0001", type="CODE", file="src/app.py", line_start=2,
                           reason="Static clue"), Evidence(evidence_id="scope", type="SCAN_SCOPE", reason="One file")])


def _website(status="NOT_DETECTED"):
    return WebsiteAnalysisResult(website_id="w1", url="https://example.com/", pages_analyzed=["https://example.com/"],
        coverage_complete=True, features=[Fact(name="login", status=status, confidence=.5,
                                                evidence_ids=["ev_0001"])],
        evidence=[Evidence(evidence_id="ev_0001", type="WEB_PAGE", url="https://example.com/", reason="Page clue"),
                  Evidence(evidence_id="scope", type="SCAN_SCOPE", reason="One page")])


def test_attach_conflict_namespace_versions_and_product_isolation(context):
    client, store, engine = context
    headers = {"Authorization": "Bearer test-service-key"}
    repo_id = _completed(store, "repository", _repo())
    web_id = _completed(store, "website", _website())
    path = "/v1/products/1/twin"
    assert client.post(path + "/analyses", json={"company_id": 2, "analysis_id": repo_id,
                                                   "kind": "repository"}, headers=headers).status_code == 404
    assert client.post("/v1/products/2/twin/analyses", json={"company_id": 2, "analysis_id": repo_id,
        "kind": "repository"}, headers=headers).status_code == 404
    first = client.post(path + "/analyses", json={"company_id": 1, "analysis_id": repo_id,
                                                 "kind": "repository"}, headers=headers)
    assert first.status_code == 201, first.text
    second = client.post(path + "/analyses", json={"company_id": 1, "analysis_id": web_id,
                                                  "kind": "website"}, headers=headers)
    assert second.status_code == 201, second.text
    body = second.json()
    assert body["version"] == 2
    facts = [f for f in body["facts"] if f["name"] == "login"]
    assert {f["status"] for f in facts} == {"PRESENT", "NOT_DETECTED"}
    assert {f["evidence"][0]["evidence_id"] for f in facts} == {repo_id + ":ev_0001", web_id + ":ev_0001"}
    assert body["conflicts"] and body["conflicts"][0]["name"] == "login"
    assert client.post(path + "/analyses", json={"company_id": 1, "analysis_id": repo_id,
        "kind": "repository"}, headers=headers).status_code == 409
    previous = client.get(path + "/versions/1?company_id=1", headers=headers).json()
    assert len(previous["facts"]) == 1 and not previous["conflicts"]
    ref = client.get(path + f"/analysis-refs/{repo_id}?company_id=1", headers=headers).json()
    assert ref["result"]["features"][0]["status"] == "PRESENT"
    assert len(ref["result_sha256"]) == 64
    with Session(engine) as db:
        assert db.get(Product, 1).collects_health_data is True


def test_manual_confirmation_correction_and_unknown(context):
    client, store, _ = context
    headers = {"Authorization": "Bearer test-service-key"}
    path = "/v1/products/1/twin"
    analysis_id = _completed(store, "repository", _repo("UNKNOWN"))
    assert client.post(path + "/analyses", json={"company_id": 1, "analysis_id": analysis_id,
        "kind": "repository"}, headers=headers).status_code == 201
    manual = client.post(path + "/facts", json={"company_id": 1, "group": "features",
        "fact": {"name": "login", "status": "PRESENT", "confidence": 1}, "note": "Observed by operator"},
        headers=headers)
    assert manual.status_code == 201, manual.text
    assert manual.json()["conflicts"] == []  # UNKNOWN does not assert absence.
    source = next(f for f in manual.json()["facts"] if f["source_kind"] == "REPOSITORY")
    confirmed = client.post(path + f"/facts/{source['id']}/confirm", json={"company_id": 1,
        "actor_label": "reviewer", "note": "Checked source"}, headers=headers)
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["decisions"][0]["action"] == "CONFIRM"
    assert any(f["confirmation_status"] == "CONFIRMED" for f in confirmed.json()["facts"])
    current_source = next(f for f in confirmed.json()["facts"] if f["source_kind"] == "REPOSITORY")
    correction = client.post(path + f"/facts/{current_source['id']}/correct", json={"company_id": 1,
        "actor_label": "reviewer", "note": "Runtime observation", "fact": {"name": "login", "status": "PARTIAL",
        "confidence": .9}}, headers=headers)
    assert correction.status_code == 200, correction.text
    assert correction.json()["version"] == 4
    assert any(f["confirmation_status"] == "CORRECTED" for f in correction.json()["facts"])
    assert any(f["source_kind"] == "USER" and f["supersedes_fact_id"] == current_source["id"]
               for f in correction.json()["facts"])
    assert client.post(path + f"/facts/{source['id']}/confirm", json={"company_id": 1},
                       headers=headers).status_code == 409
    assert len(client.get(path + "/versions?company_id=1", headers=headers).json()) == 4
    assert client.get(path + "?company_id=2", headers=headers).status_code == 404
    assert client.get(path + "?company_id=1").status_code == 401


def test_unlinked_and_unfinished_jobs_cannot_attach(context):
    client, store, _ = context
    headers = {"Authorization": "Bearer test-service-key"}
    owner = hashlib.sha256(b"test-service-key").hexdigest()
    unlinked = store.create("repository", owner)
    unlinked.status = "COMPLETED"
    unlinked.repository_analysis = _repo()
    store.save(unlinked)
    pending = store.create("website", owner, 1)
    base = "/v1/products/1/twin/analyses"
    assert client.post(base, json={"company_id": 1, "analysis_id": unlinked.analysis_id,
        "kind": "repository"}, headers=headers).status_code == 404
    assert client.post(base, json={"company_id": 1, "analysis_id": pending.analysis_id,
        "kind": "website"}, headers=headers).status_code == 409


def test_linked_submission_validates_company(context, monkeypatch):
    client, _, _ = context
    headers = {"Authorization": "Bearer test-service-key"}
    monkeypatch.setattr(website_understanding, "analyze_website", lambda request: _website())
    bad = client.post("/v1/analyze-website", json={"company_id": 2, "product_id": 1,
        "url": "https://example.com/"}, headers=headers)
    assert bad.status_code == 404
    good = client.post("/v1/analyze-website", json={"company_id": 1, "product_id": 1,
        "url": "https://example.com/"}, headers=headers)
    assert good.status_code == 202, good.text
    assert good.json()["product_id"] == 1
    result = client.get("/v1/website-analysis/" + good.json()["analysis_id"], headers=headers)
    assert result.json()["status"] == "COMPLETED"
    assert result.json()["product_id"] == 1


def test_migration_adopts_existing_job_table(tmp_path):
    db_path = tmp_path / "legacy.db"
    backend = Path(__file__).resolve().parents[1]
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db_path}",
           "PYTHONPATH": str(backend) + os.pathsep + os.environ.get("PYTHONPATH", "")}
    def upgrade(target):
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", target], cwd=backend,
                       env=env, check=True, capture_output=True, text=True)
    upgrade("0004")
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE product_understanding_jobs (analysis_id VARCHAR(64) PRIMARY KEY, "
                     "owner VARCHAR(64) NOT NULL, kind VARCHAR(16) NOT NULL, status VARCHAR(16) NOT NULL, "
                     "created_at VARCHAR(40) NOT NULL, updated_at VARCHAR(40) NOT NULL, payload TEXT NOT NULL)")
        conn.execute("INSERT INTO product_understanding_jobs VALUES (?,?,?,?,?,?,?)",
                     ("legacy", "owner", "repository", "COMPLETED", "2026", "2026", "{}"))
    upgrade("head")
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT analysis_id, product_id FROM product_understanding_jobs").fetchone() == ("legacy", None)
        assert conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name LIKE 'product_twin_%'").fetchone()[0] == 4
