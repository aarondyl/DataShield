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
