"""代表性 HTML 夹具，非真实法规核验：编码、条文引用和失败关闭。"""
from types import SimpleNamespace

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models import Regulation, RegulationEvent, RegulationVersion, RegulatorySource
from app.regintel.adapters import HttpTextAdapter, RawDocument
from app.regintel.parsing import article_units, parse_legal_text
from app.regintel.pipeline import run_ingestion


def test_official_english_html_entities_and_references_are_preserved():
    raw = RawDocument(content='<p>Article&nbsp;50</p><p>Transparency</p>'
        '<p>Providers shall disclose A &amp; B under Article 3(4).</p>'
        '<p>Article&#160;51</p><p>Classification</p><p>Providers shall notify.</p>'
        '<p>ANNEX I</p><p>Annex material must not enter Article 51.</p>', content_type='text/html')
    text = HttpTextAdapter(None).extract_content(raw)
    articles = article_units(parse_legal_text(text, 'eu_english'))
    assert [a.unit_number for a in articles] == ['Article 50', 'Article 51']
    assert 'A & B under Article 3(4)' in articles[0].text
    assert 'Annex material' not in articles[1].text


def test_duplicate_articles_fail_without_publishing_version_or_event(monkeypatch, tmp_path):
    from app.regintel import pipeline
    monkeypatch.setattr(pipeline, 'BACKEND_ROOT', tmp_path)
    content = 'Article 50\nProviders shall inform users.\nArticle 50\nDuplicate shall not silently overwrite.'
    monkeypatch.setattr(pipeline, 'get_adapter', lambda source: SimpleNamespace(
        fetch=lambda: RawDocument(content=content), extract_content=lambda raw: raw.content))
    engine = create_engine(f'sqlite:///{tmp_path / "cloud-fixture.db"}')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        regulation = Regulation(name='TEST FIXTURE', jurisdiction='EU')
        db.add(regulation); db.flush()
        source = RegulatorySource(regulation_id=regulation.id, source_name='TEST FIXTURE', parser_type='eu_english')
        db.add(source); db.commit()
        run = run_ingestion(db, source, use_llm=False, language='en')
        assert run.status == 'FAILED' and '重复法律条号' in run.error
        assert db.scalar(select(RegulationVersion)) is None
        assert db.scalar(select(RegulationEvent)) is None
        assert regulation.current_version_id is None


def test_first_import_emits_sync_bundle_and_unchanged_retry_is_idempotent(monkeypatch, tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api import regintel
    from app.db.session import get_db
    from app.regintel import pipeline
    monkeypatch.setattr(pipeline, 'BACKEND_ROOT', tmp_path)
    content = 'Article 50\nTransparency\nProviders shall inform users about AI.'
    monkeypatch.setattr(pipeline, 'get_adapter', lambda source: SimpleNamespace(
        fetch=lambda: RawDocument(content=content), extract_content=lambda raw: raw.content))
    engine = create_engine(f'sqlite:///{tmp_path / "first-import.db"}', connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        regulation = Regulation(name='TEST FIXTURE', jurisdiction='EU')
        db.add(regulation); db.flush()
        source = RegulatorySource(regulation_id=regulation.id, source_name='TEST FIXTURE', parser_type='eu_english')
        db.add(source); db.commit()
        run = run_ingestion(db, source, use_llm=False)
        assert run.status == 'COMPLETED' and run.event_id is not None
        event = db.get(RegulationEvent, run.event_id)
        assert event.payload['initial_import'] is True
        assert event.payload['requirement_ids'] and event.payload['affected_legal_unit_ids']
        event_id = event.event_id
        retry = run_ingestion(db, source, use_llm=False, language='en')
        assert retry.status == 'NO_CHANGE'
        assert len(db.scalars(select(RegulationEvent)).all()) == 1
    api = FastAPI(); api.include_router(regintel.router, prefix='/api')
    def database():
        with Session(engine) as db:
            yield db
    api.dependency_overrides[get_db] = database
    client = TestClient(api)
    page = client.get('/api/v1/sync/events').json()
    assert page['events'][0]['event_id'] == event_id
    bundle = client.get(f'/api/v1/sync/events/{event_id}/bundle').json()
    assert bundle['requirements'] and bundle['legal_units']
    assert bundle['requirements'][0]['subject_type'] == 'provider'
