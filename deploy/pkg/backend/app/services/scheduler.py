"""法规来源定时轮询（MVP 可选，APScheduler 每日任务）。

默认关闭：``SCHEDULER_ENABLED=true`` 时启动，按 ``SCHEDULER_INTERVAL_HOURS``
（默认 24 小时）对所有 is_active 来源跑一次入库流水线。
若官方提供 API/RSS，后续应优先改为订阅式来源，而非网页硬爬。
"""

from __future__ import annotations

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import RegulatorySource
from app.regintel.pipeline import run_ingestion


def poll_active_sources() -> None:
    """对所有启用的来源执行一次抓取入库（版本未变则记 NO_CHANGE）。"""
    with SessionLocal() as db:
        sources = db.scalars(
            select(RegulatorySource)
            .where(RegulatorySource.is_active.is_(True))
            .order_by(RegulatorySource.priority)
        ).all()
        for source in sources:
            run_ingestion(db, source)


def start_scheduler():
    """启动后台定时器；未启用或 APScheduler 不可用时返回 None。"""
    settings = get_settings()
    if not settings.scheduler_enabled:
        return None
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError:
        return None
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        poll_active_sources,
        trigger="interval",
        hours=settings.scheduler_interval_hours,
        id="regintel_polling",
        name="法规来源定时轮询",
    )
    scheduler.start()
    return scheduler
