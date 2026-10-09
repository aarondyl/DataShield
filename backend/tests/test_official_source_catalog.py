from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models import Regulation, RegulatorySource
from app.regintel.adapters import HttpTextAdapter, RawDocument
from app.services.cloud_source_catalog import seed_cloud_official_sources
from app.services import scheduler as scheduler_service


def test_official_source_catalog_is_idempotent_and_only_records_source_metadata():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        assert seed_cloud_official_sources(db) == 6
        assert seed_cloud_official_sources(db) == 0
        regs = db.scalars(select(Regulation)).all()
        sources = db.scalars(select(RegulatorySource)).all()
        assert {reg.short_name for reg in regs} == {"PIPL", "DSL", "GDPR"}
        assert all(reg.published_at and reg.effective_at for reg in regs)
        assert len(sources) == 3
        assert {source.source_name for source in sources if source.is_active} == {"PIPL", "DSL"}
        assert all(source.source_type == "html" for source in sources)
        assert all(reg.current_version_id is None for reg in regs)
    engine.dispose()


def test_html_extraction_skips_navigation_and_decodes_entities():
    adapter = HttpTextAdapter(object())
    document = RawDocument(
        content="<nav>导航</nav><main><h1>第一章</h1><p>第一条&nbsp;处理个人信息。</p><script>伪造内容</script></main>",
        content_type="text/html",
    )
    text = adapter.extract_content(document)
    assert "第一条 处理个人信息。" in text
    assert "导航" not in text
    assert "伪造内容" not in text


def test_http_source_retries_transient_server_errors(monkeypatch):
    import httpx
    import app.regintel.adapters as adapters

    replies = iter([
        httpx.Response(503, request=httpx.Request("GET", "https://example.org/law")),
        httpx.Response(200, text="<p>正文</p>", headers={"content-type": "text/html"},
                       request=httpx.Request("GET", "https://example.org/law")),
    ])
    monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: next(replies))
    monkeypatch.setattr(adapters.time, "sleep", lambda _: None)
    raw = HttpTextAdapter(type("Source", (), {"fetch_url": "https://example.org/law"})()).fetch()
    assert raw.content == "<p>正文</p>"


def test_source_snapshot_stores_original_bytes_and_separate_raw_hash(tmp_path, monkeypatch):
    import hashlib
    from app.regintel import pipeline

    monkeypatch.setattr(pipeline, "BACKEND_ROOT", tmp_path)
    raw = b"<article>raw &amp; official</article>"
    uri, raw_hash = pipeline._write_snapshot(9, "normalized-hash", raw)
    assert (tmp_path / uri).read_bytes() == raw
    assert raw_hash == hashlib.sha256(raw).hexdigest()
    assert raw.raw_bytes == "<p>正文</p>".encode("utf-8")


def test_raw_snapshot_preserves_exact_response_bytes_and_hash(tmp_path, monkeypatch):
    import hashlib
    import app.regintel.pipeline as pipeline

    monkeypatch.setattr(pipeline, "BACKEND_ROOT", tmp_path)
    monkeypatch.setattr(pipeline, "SNAPSHOT_DIR", "snapshots")
    raw_bytes = b"<html><p>Official response</p></html>\r\n"
    uri, raw_hash = pipeline._write_snapshot(7, "a" * 64, raw_bytes)
    snapshot_path = tmp_path / uri

    assert snapshot_path.read_bytes() == raw_bytes
    assert raw_hash == hashlib.sha256(raw_bytes).hexdigest()


def test_scheduler_registers_warmup_and_daily_single_instance_jobs(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("RUNTIME_MODE", "cloud")
    monkeypatch.setenv("SCHEDULER_ENABLED", "true")
    monkeypatch.setenv("SCHEDULER_INTERVAL_HOURS", "24")
    get_settings.cache_clear()
    scheduler = scheduler_service.start_scheduler()
    assert scheduler is not None
    try:
        jobs = {job.id: job for job in scheduler.get_jobs()}
        assert {"regintel_polling", "regintel_initial_poll"} <= jobs.keys()
        assert jobs["regintel_polling"].max_instances == 1
    finally:
        scheduler.shutdown(wait=False)
        get_settings.cache_clear()
