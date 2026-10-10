"""A first official-law import must be visible to Desktop incremental sync."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.session import get_db
from app.models import Regulation, RegulationChange, RegulatorySource
from app.regintel import adapters, pipeline
from app.api import regintel


def test_first_import_publishes_sync_event_and_bundle(tmp_path, monkeypatch):
    content = """第一章 总则\n第一条 个人信息处理者应当依法处理个人信息。\n第二条 个人信息处理者不得泄露个人信息。\n"""
    source_file = tmp_path / "official-law.txt"
    source_file.write_text(content, encoding="utf-8")
    monkeypatch.setattr(adapters, "BACKEND_ROOT", tmp_path)
    monkeypatch.setattr(pipeline, "BACKEND_ROOT", tmp_path)
    monkeypatch.setattr(pipeline, "index_legal_chunks", lambda _chunks: None)

    engine = create_engine(f"sqlite:///{tmp_path / 'cloud.db'}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as db:
        regulation = Regulation(
            name="测试官方法规", jurisdiction="CN", official_identifier="CN:TEST-1",
            canonical_source_url="https://example.gov.cn/law/1",
        )
        db.add(regulation)
        db.flush()
        source = RegulatorySource(
            regulation_id=regulation.id, jurisdiction="CN", authority="官方发布机关",
            source_name="官方法规来源", base_url=regulation.canonical_source_url,
            fetch_url=f"file://{source_file}", source_type="local_file", parser_type="cn_law",
        )
        db.add(source)
        db.commit()
        run = pipeline.run_ingestion(db, source, use_llm=False, default_subject="个人信息处理者")
        assert run.status == "COMPLETED", run.error
        assert run.changes_count == 2
        assert run.event_id is not None
        changes = db.scalars(select(RegulationChange).where(RegulationChange.regulation_id == regulation.id)).all()
        assert len(changes) == 2
        assert all(change.change_type == "ADDED" and change.from_version_id is None for change in changes)

    app = FastAPI()

    def override_db():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    app.include_router(regintel.router, prefix="/api")
    with TestClient(app) as client:
        page = client.get("/api/v1/sync/events", params={"jurisdiction": "CN"})
        assert page.status_code == 200, page.text
        events = page.json()["events"]
        assert len(events) == 1
        assert events[0]["event_id"]
        bundle_response = client.get(f"/api/v1/sync/events/{events[0]['event_id']}/bundle")
        assert bundle_response.status_code == 200, bundle_response.text
        bundle = bundle_response.json()
        assert bundle["regulation"]["source_url"] == "https://example.gov.cn/law/1"
        assert len(bundle["legal_units"]) == 3
        assert bundle["requirements"]

