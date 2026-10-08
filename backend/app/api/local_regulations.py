"""Desktop-only presentation and manual sync APIs for public regulation data."""

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from app.db.session import SessionLocal
from app.models import Requirement

from app.core.config import get_settings
from app.local_regulations.cache import LocalRegulationCache
from app.local_regulations.client import CloudSyncClient

router = APIRouter(prefix="/v1/local-regulations", tags=["Local regulation sync"])


def _scope(jurisdiction: str | None) -> str:
    return f"all:jurisdiction={jurisdiction or '*'}"


def _cache() -> LocalRegulationCache:
    return LocalRegulationCache(get_settings().local_regulation_cache_path)


@router.get("/status")
def status(jurisdiction: str | None = Query(default=None)) -> dict:
    """Return local-cache state only; this endpoint never contacts Cloud."""
    scope = _scope(jurisdiction)
    state = _cache().status(scope)
    return {"scope": scope, "jurisdiction": jurisdiction, "using_local_cache": bool(state["offline"]), **state}


@router.get("/events")
def events(limit: int = Query(default=100, ge=1, le=200)) -> list[dict]:
    """Cached public regulation events with their local evidence source metadata."""
    return _cache().events(limit)


@router.get("/requirements")
def requirements() -> list[dict]:
    """Local materialized Requirements eligible for a user-initiated scan."""
    with SessionLocal() as db:
        rows = db.scalars(select(Requirement).where(Requirement.status != "SUPERSEDED").order_by(Requirement.id)).all()
        return [{"id": row.id, "summary": row.summary, "regulation_id": row.regulation_id, "version_id": row.version_id, "status": row.status} for row in rows]


@router.post("/sync")
def sync(jurisdiction: str | None = Query(default=None)) -> dict:
    """Pull public Cloud regulation events; never uploads local tenant information."""
    settings = get_settings()
    if not settings.cloud_regintel_base_url.startswith("https://"):
        raise HTTPException(503, "未配置 HTTPS Cloud 法规同步地址，正在使用本地缓存")
    cache = _cache()
    try:
        cursor = CloudSyncClient(settings.cloud_regintel_base_url, cache).sync(jurisdiction=jurisdiction)
    except ConnectionError as exc:
        raise HTTPException(503, "Cloud 法规服务不可用，正在使用本地缓存") from exc
    return {"cursor": cursor, "status": cache.status(_scope(jurisdiction)), "events": cache.events()}
