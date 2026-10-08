"""全局法规智能层 API（/api/v1）。

对 User Agent 稳定提供：
- ``POST /v1/legal-search``：语义法条检索；
- ``GET  /v1/requirements/{id}`` / ``GET /v1/legal-units/{id}``：义务与条文证据追溯；
- ``GET  /v1/regulations/{id}`` / ``GET /v1/regulations/{id}/versions``：法规与版本；
- ``GET  /v1/changes/{id}``：条级变化；
- ``GET  /v1/sources`` + ``POST /v1/sources/{id}/ingest``：来源与入库流水线；
- ``GET  /v1/events``：regulation.change.ready 事件流。
"""

import hashlib
import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import (
    IngestionRun,
    LegalUnit,
    Regulation,
    RegulationChange,
    RegulationEvent,
    RegulationVersion,
    RegulatorySource,
    Requirement,
)
from app.rag.embeddings import embed_texts_with_fallback
from app.regintel.pipeline import run_ingestion
from app.regintel.retrieval import get_legal_chunk_store
from app.schemas.regintel import (
    ChangeOut,
    EventOut,
    IngestionRunOut,
    LegalSearchRequest,
    LegalSearchResponse,
    LegalSearchResultItem,
    LegalUnitOut,
    RegulationInfoOut,
    RequirementOut,
    SourceOut,
    VersionOut,
    SyncPage,
)

router = APIRouter(prefix="/v1", tags=["regintel"])


def _require_cloud_operator(authorization: str | None = Header(default=None)) -> None:
    from app.core.config import get_settings

    settings = get_settings()
    # This router is also reused by the existing single-process Web deployment.
    # The Cloud runtime is the shared public service, so only it enforces this
    # operator boundary; preserving Web behaviour avoids silently changing the
    # legacy deployment contract.
    if settings.runtime_mode != "cloud":
        return
    expected = settings.cloud_admin_token
    supplied = authorization.removeprefix("Bearer ") if authorization else ""
    if not expected:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Cloud operator API is not configured")
    if not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Cloud operator authorization required")


# ---------------------------------------------------------------------------
# Legal Search API
# ---------------------------------------------------------------------------


@router.post("/legal-search", response_model=LegalSearchResponse)
def legal_search(body: LegalSearchRequest, db: Session = Depends(get_db)) -> LegalSearchResponse:
    """语义法条检索：query 向量化后在 pgvector（或本地索引）中做相似度检索。"""
    if not body.query.strip():
        raise HTTPException(status_code=400, detail="query 不能为空")
    query_embedding = embed_texts_with_fallback([body.query])[0]
    store = get_legal_chunk_store()
    hits = store.search(
        query_embedding,
        top_k=body.top_k * 4,
        jurisdictions=body.jurisdictions or None,
        regulation_ids=body.regulation_ids or None,
        current_only=body.current_only,
    )
    if hits and hits[0].get("score") is not None:
        # 本地哈希向量的混合检索：向量分 + 查询词面覆盖率重排（pg 模式由 pgvector 排序，score=None）
        bigrams = {body.query[i : i + 2] for i in range(len(body.query) - 1)} or {body.query}
        for hit in hits:
            coverage = sum(1 for bg in bigrams if bg in hit.get("content", "")) / len(bigrams)
            hit["score"] = round(0.7 * hit["score"] + 0.3 * coverage, 6)
        hits.sort(key=lambda h: -(h["score"] or 0.0))
    hits = hits[: body.top_k]
    results: list[LegalSearchResultItem] = []
    for hit in hits:
        requirement_ids: list[int] = []
        summary = ""
        if hit.get("legal_unit_id"):
            reqs = db.scalars(
                select(Requirement).where(
                    Requirement.legal_unit_id == hit["legal_unit_id"],
                    Requirement.status != "SUPERSEDED",
                )
            ).all()
            requirement_ids = [r.id for r in reqs]
            summary = reqs[0].summary if reqs else ""
        results.append(
            LegalSearchResultItem(
                chunk_id=hit["chunk_id"],
                regulation_id=hit["regulation_id"],
                regulation_name=hit.get("regulation_name", ""),
                version_id=hit.get("version_id") or 0,
                legal_unit_id=hit.get("legal_unit_id"),
                article=hit.get("article", ""),
                requirement_ids=requirement_ids,
                content=hit.get("content", ""),
                summary=summary,
                source_url=hit.get("source_url", ""),
                similarity_score=hit.get("score"),
            )
        )
    return LegalSearchResponse(results=results)


# ---------------------------------------------------------------------------
# Requirement / Legal Unit（Evidence）API
# ---------------------------------------------------------------------------


@router.get("/requirements", response_model=list[RequirementOut])
def list_requirements(
    regulation_id: int | None = None,
    version_id: int | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
) -> list[RequirementOut]:
    """义务单元列表（可按法规/版本/状态过滤，默认只返回当前版本）。"""
    stmt = select(Requirement)
    if regulation_id is not None:
        stmt = stmt.where(Requirement.regulation_id == regulation_id)
    if version_id is not None:
        stmt = stmt.where(Requirement.version_id == version_id)
    elif regulation_id is not None:
        regulation = db.get(Regulation, regulation_id)
        if regulation and regulation.current_version_id:
            stmt = stmt.where(Requirement.version_id == regulation.current_version_id)
    if status:
        stmt = stmt.where(Requirement.status == status)
    return [RequirementOut.model_validate(r) for r in db.scalars(stmt.order_by(Requirement.id)).all()]


@router.get("/requirements/{requirement_id}", response_model=RequirementOut)
def get_requirement(requirement_id: int, db: Session = Depends(get_db)) -> RequirementOut:
    """单条义务单元。"""
    requirement = db.get(Requirement, requirement_id)
    if requirement is None:
        raise HTTPException(status_code=404, detail="义务单元不存在")
    return RequirementOut.model_validate(requirement)


@router.get("/legal-units/{unit_id}", response_model=LegalUnitOut)
def get_legal_unit(unit_id: int, db: Session = Depends(get_db)) -> LegalUnitOut:
    """法律单元证据：条文文本 + 所属法规/版本 + 官方来源 URL。"""
    unit = db.get(LegalUnit, unit_id)
    if unit is None:
        raise HTTPException(status_code=404, detail="法律单元不存在")
    version = db.get(RegulationVersion, unit.version_id)
    regulation = db.get(Regulation, version.regulation_id) if version else None
    out = LegalUnitOut.model_validate(unit)
    if version:
        out.version_number = version.version_number
    if regulation:
        out.regulation_id = regulation.id
        out.regulation_name = regulation.name
        out.official_source_url = regulation.canonical_source_url or regulation.source_url
        out.is_current_version = regulation.current_version_id == unit.version_id
    return out


# ---------------------------------------------------------------------------
# Regulation / Version / Change API
# ---------------------------------------------------------------------------


def _regulation_info(db: Session, regulation: Regulation) -> RegulationInfoOut:
    """组装法规全局元数据（当前版本号 + 当前版本条款数/义务数）。"""
    out = RegulationInfoOut.model_validate(regulation)
    if regulation.current_version_id:
        version = db.get(RegulationVersion, regulation.current_version_id)
        if version:
            out.current_version_number = version.version_number
        out.article_count = db.scalar(
            select(func.count())
            .select_from(LegalUnit)
            .where(LegalUnit.version_id == regulation.current_version_id, LegalUnit.unit_type == "article")
        ) or 0
        out.requirement_count = db.scalar(
            select(func.count())
            .select_from(Requirement)
            .where(Requirement.version_id == regulation.current_version_id)
        ) or 0
    return out


@router.get("/regulations", response_model=list[RegulationInfoOut])
def list_regulations_v1(db: Session = Depends(get_db)) -> list[RegulationInfoOut]:
    """法规列表（只含纳入全局法规智能层、已有版本的法规）。"""
    regulations = db.scalars(
        select(Regulation).where(Regulation.current_version_id.is_not(None)).order_by(Regulation.id)
    ).all()
    return [_regulation_info(db, r) for r in regulations]


@router.get("/regulations/{regulation_id}", response_model=RegulationInfoOut)
def get_regulation_v1(regulation_id: int, db: Session = Depends(get_db)) -> RegulationInfoOut:
    """法规元数据：canonical source / 当前版本 / 生效日期 / 机关 / 法域。"""
    regulation = db.get(Regulation, regulation_id)
    if regulation is None:
        raise HTTPException(status_code=404, detail="法规不存在")
    return _regulation_info(db, regulation)


@router.get("/regulations/{regulation_id}/versions", response_model=list[VersionOut])
def list_versions(regulation_id: int, db: Session = Depends(get_db)) -> list[VersionOut]:
    """法规的全部历史版本（新版本绝不覆盖旧版本）。"""
    if db.get(Regulation, regulation_id) is None:
        raise HTTPException(status_code=404, detail="法规不存在")
    versions = db.scalars(
        select(RegulationVersion)
        .where(RegulationVersion.regulation_id == regulation_id)
        .order_by(RegulationVersion.version_number)
    ).all()
    return [VersionOut.model_validate(v) for v in versions]


@router.get("/changes", response_model=list[ChangeOut])
def list_changes(regulation_id: int | None = None, db: Session = Depends(get_db)) -> list[ChangeOut]:
    """条级变化列表（可按法规过滤）。"""
    stmt = select(RegulationChange).order_by(RegulationChange.detected_at.desc())
    if regulation_id is not None:
        stmt = stmt.where(RegulationChange.regulation_id == regulation_id)
    return [_change_out(db, c) for c in db.scalars(stmt).all()]


@router.get("/changes/{change_id}", response_model=ChangeOut)
def get_change(change_id: int, db: Session = Depends(get_db)) -> ChangeOut:
    """单条变化：change type / 新旧版本 / 涉及法律单元 / 语义摘要 / requirement ids / 来源。"""
    change = db.get(RegulationChange, change_id)
    if change is None:
        raise HTTPException(status_code=404, detail="变化记录不存在")
    return _change_out(db, change)


def _change_out(db: Session, change: RegulationChange) -> ChangeOut:
    regulation = db.get(Regulation, change.regulation_id)
    unit = db.get(LegalUnit, change.legal_unit_id) if change.legal_unit_id else None
    out = ChangeOut.model_validate(change)
    if regulation:
        out.regulation_name = regulation.name
        out.source_url = regulation.canonical_source_url or regulation.source_url
    if unit:
        out.article = unit.unit_number
    return out


# ---------------------------------------------------------------------------
# Source / Ingestion / Event API
# ---------------------------------------------------------------------------


@router.get("/sources", response_model=list[SourceOut])
def list_sources(db: Session = Depends(get_db)) -> list[SourceOut]:
    """官方来源列表。"""
    sources = db.scalars(select(RegulatorySource).order_by(RegulatorySource.priority)).all()
    return [SourceOut.model_validate(s) for s in sources]


@router.post("/sources/{source_id}/ingest", response_model=IngestionRunOut, dependencies=[Depends(_require_cloud_operator)])
def ingest_source(source_id: int, db: Session = Depends(get_db)) -> IngestionRunOut:
    """触发一次来源抓取 + 入库流水线（版本检测 / diff / 义务提取 / 增量向量化）。"""
    source = db.get(RegulatorySource, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="来源不存在")
    run = run_ingestion(db, source)
    if run.status == "FAILED":
        raise HTTPException(status_code=502, detail=f"入库流水线失败：{run.error}")
    return IngestionRunOut.model_validate(run)


@router.get("/ingestion-runs", response_model=list[IngestionRunOut])
def list_ingestion_runs(
    regulation_id: int | None = None, db: Session = Depends(get_db)
) -> list[IngestionRunOut]:
    """入库流水线运行历史。"""
    stmt = select(IngestionRun).order_by(IngestionRun.id.desc())
    if regulation_id is not None:
        stmt = stmt.where(IngestionRun.regulation_id == regulation_id)
    return [IngestionRunOut.model_validate(r) for r in db.scalars(stmt).all()]


@router.get("/events", response_model=list[EventOut])
def list_events(db: Session = Depends(get_db)) -> list[EventOut]:
    """已发布的 regulation.change.ready 事件列表。"""
    events = db.scalars(select(RegulationEvent).order_by(RegulationEvent.id)).all()
    return [EventOut.model_validate(e) for e in events]


@router.get("/sync/events", response_model=SyncPage)
def sync_events(
    cursor: int = 0,
    snapshot_cursor: int | None = None,
    limit: int = 100,
    jurisdiction: str | None = None,
    db: Session = Depends(get_db),
) -> SyncPage:
    """供 Local 拉取法规事件的稳定分页接口。

    首页固定 snapshot_cursor；后续页必须携带该值。排序使用单调数据库事件序号，
    而非可能相同的时间戳。新事件不会混入已固定的分页范围。
    """
    if limit < 1 or limit > 200:
        raise HTTPException(422, detail="limit 必须在 1 到 200 之间")
    upper = snapshot_cursor if snapshot_cursor is not None else (db.scalar(select(func.max(RegulationEvent.id))) or 0)
    if cursor < 0 or cursor > upper:
        raise HTTPException(422, detail="cursor 超出快照范围")
    stmt = select(RegulationEvent).where(RegulationEvent.id > cursor, RegulationEvent.id <= upper).order_by(RegulationEvent.id)
    if jurisdiction:
        stmt = stmt.join(Regulation, Regulation.id == RegulationEvent.regulation_id).where(Regulation.jurisdiction == jurisdiction)
    rows = db.scalars(stmt.limit(limit + 1)).all()
    page_rows, extra = rows[:limit], len(rows) > limit
    next_cursor = page_rows[-1].id if page_rows else cursor
    return SyncPage(snapshot_cursor=upper, next_cursor=next_cursor, has_more=extra, events=[EventOut.model_validate(row) for row in page_rows])


@router.get("/sync/events/{event_id}/bundle")
def sync_event_bundle(event_id: str, db: Session = Depends(get_db)) -> dict:
    """返回本地缓存一条事件所需的法规对象，使用稳定跨端键而非数据库主键。"""
    event = db.scalar(select(RegulationEvent).where(RegulationEvent.event_id == event_id))
    if event is None: raise HTTPException(404, detail="法规事件不存在")
    regulation = db.get(Regulation, event.regulation_id)
    version = db.get(RegulationVersion, event.version_id)
    if regulation is None or version is None: raise HTTPException(409, detail="法规事件引用未就绪")
    reg_key = regulation.official_identifier or f"{regulation.jurisdiction}:{regulation.name}"
    version_key = f"{reg_key}:v{version.version_number}"
    units = db.scalars(select(LegalUnit).where(LegalUnit.version_id == version.id).order_by(LegalUnit.order_index)).all()
    requirements = db.scalars(select(Requirement).where(Requirement.version_id == version.id).order_by(Requirement.id)).all()
    unit_key = {u.id: f"{version_key}:{u.path or u.unit_number}" for u in units}
    return {"schema_version":"1.0", "event": EventOut.model_validate(event).model_dump(mode="json"),
      "regulation": {"key":reg_key,"name":regulation.name,"jurisdiction":regulation.jurisdiction,"status":regulation.status,"source_url":regulation.canonical_source_url or regulation.source_url,"effective_at":regulation.effective_at},
      "version": {"key":version_key,"number":version.version_number,"content_hash":version.content_hash,"is_current":version.is_current,"source_url":version.source_url,"effective_from":version.effective_from,"effective_to":version.effective_to},
      "legal_units":[{"key":unit_key[u.id],"unit_number":u.unit_number,"heading":u.heading,"text":u.text,"path":u.path} for u in units],
      "requirements":[{"key":hashlib.sha256(f'{unit_key.get(r.legal_unit_id, version_key)}:{r.action_type}:{r.summary}'.encode()).hexdigest(),"legal_unit_key":unit_key.get(r.legal_unit_id),"type":r.requirement_type,"action":r.action_type,"summary":r.summary,"status":r.status,"conditions":r.conditions_json,"exceptions":r.exceptions_json,"subject_type":r.subject_type,"object_type":r.object_type,"confidence":r.confidence,"effective_from":r.effective_from,"effective_to":r.effective_to} for r in requirements]}


@router.get("/events/{event_id}", response_model=EventOut)
def get_event(event_id: str, db: Session = Depends(get_db)) -> EventOut:
    """按对外事件 id（evt_xxxxxx）查询事件。"""
    event = db.scalar(select(RegulationEvent).where(RegulationEvent.event_id == event_id))
    if event is None:
        raise HTTPException(status_code=404, detail="事件不存在")
    return EventOut.model_validate(event)
