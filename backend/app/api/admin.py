"""管理后台 API（/api/v1/admin）：平台总览、用户/企业/法规管理与演示数据清理。

鉴权：请求头 ``X-Admin-Key`` 需与环境变量 ``ADMIN_API_KEY`` 完全一致
（``hmac.compare_digest`` 恒定时间比较）。未配置密钥时全部端点返回 503，
避免裸奔暴露管理面。
"""

import hmac
import platform
import secrets
import string
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.passwords import hash_password
from app.core.runtime import STARTED_AT
from app.db.session import db_kind, get_db
from app.models import (
    AnalysisRun,
    Assessment,
    Company,
    ComplianceAction,
    DeveloperIssue,
    EvaluationSession,
    Feedback,
    FeedbackCandidate,
    FeedbackCandidateRequirement,
    Finding,
    FindingEvidence,
    FindingRequirement,
    ImpactResult,
    IngestionRun,
    LegalChunk,
    LegalUnit,
    Product,
    ProductTwinAnalysisRef,
    ProductTwinDecision,
    ProductTwinFact,
    ProductTwinVersion,
    Regulation,
    RegulationArticle,
    RegulationChange,
    RegulationEvent,
    RegulationVersion,
    RegulatorySource,
    Remediation,
    RemediationEvidence,
    RemediationRequirement,
    Requirement,
    SdkScan,
    SourceSnapshot,
    TenantAgentRun,
    TenantMissingContextItem,
    User,
)
from app.rag.retrieval import rebuild_local_store_from_db
from app.regintel.retrieval import rebuild_legal_chunk_store_from_db
from app.services.seed_regintel import seed_regintel_if_empty


def require_admin(x_admin_key: str | None = Header(default=None)) -> None:
    """校验 X-Admin-Key；未配置 ADMIN_API_KEY 时关闭整个管理面。"""
    expected = get_settings().admin_api_key
    if not expected:
        raise HTTPException(503, "Admin API is not configured")
    if not x_admin_key or not hmac.compare_digest(x_admin_key, expected):
        raise HTTPException(401, "Invalid admin key")


router = APIRouter(prefix="/v1/admin", tags=["Admin"], dependencies=[Depends(require_admin)])


def _count(db: Session, model) -> int:
    return db.scalar(select(func.count()).select_from(model)) or 0


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------


@router.get("/overview")
def overview(db: Session = Depends(get_db)):
    """平台级计数总览（用户/企业/产品/分析运行/发现/法规层/活跃会话）。"""
    now = datetime.utcnow()
    active_sessions = db.scalar(
        select(func.count())
        .select_from(EvaluationSession)
        .where(EvaluationSession.revoked_at.is_(None), EvaluationSession.expires_at > now)
    ) or 0
    return {
        "users": _count(db, User),
        "companies": _count(db, Company),
        "products": _count(db, Product),
        "analysis_runs": _count(db, AnalysisRun),
        "tenant_agent_runs": _count(db, TenantAgentRun),
        "findings": _count(db, Finding),
        "regulations": _count(db, Regulation),
        "legal_units": _count(db, LegalUnit),
        "active_sessions": active_sessions,
    }


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


def _user_row(db: Session, user: User, now: datetime) -> dict:
    company = db.get(Company, user.company_id)
    active_sessions = db.scalar(
        select(func.count())
        .select_from(EvaluationSession)
        .where(
            EvaluationSession.user_id == user.id,
            EvaluationSession.revoked_at.is_(None),
            EvaluationSession.expires_at > now,
        )
    ) or 0
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "company_id": user.company_id,
        "company_name": company.name if company else "",
        "edition": user.edition,
        "email_verified": user.email_verified,
        "disabled": user.disabled,
        "created_at": user.created_at,
        "last_login_at": user.last_login_at,
        "active_sessions": active_sessions,
    }


@router.get("/users")
def list_users(db: Session = Depends(get_db)):
    now = datetime.utcnow()
    return [_user_row(db, u, now) for u in db.scalars(select(User).order_by(User.id)).all()]


def _get_user_or_404(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    return user


@router.post("/users/{user_id}/disable")
def disable_user(user_id: int, db: Session = Depends(get_db)):
    """禁用账户：标记 disabled 并吊销该用户所有未吊销会话。"""
    user = _get_user_or_404(db, user_id)
    user.disabled = True
    now = datetime.utcnow()
    sessions = db.scalars(
        select(EvaluationSession).where(
            EvaluationSession.user_id == user.id, EvaluationSession.revoked_at.is_(None)
        )
    ).all()
    for session in sessions:
        session.revoked_at = now
    db.commit()
    return {"id": user.id, "disabled": True, "revoked_sessions": len(sessions)}


@router.post("/users/{user_id}/enable")
def enable_user(user_id: int, db: Session = Depends(get_db)):
    user = _get_user_or_404(db, user_id)
    user.disabled = False
    db.commit()
    return {"id": user.id, "disabled": False}


@router.post("/users/{user_id}/reset-password")
def reset_password(user_id: int, db: Session = Depends(get_db)):
    """重置为随机 10 位密码并返回给管理员（只显示这一次）。"""
    user = _get_user_or_404(db, user_id)
    alphabet = string.ascii_letters + string.digits
    new_password = "".join(secrets.choice(alphabet) for _ in range(10))
    user.password_hash = hash_password(new_password)
    db.commit()
    return {"id": user.id, "new_password": new_password}


# ---------------------------------------------------------------------------
# Companies
# ---------------------------------------------------------------------------


@router.get("/companies")
def list_companies(db: Session = Depends(get_db)):
    rows = []
    for company in db.scalars(select(Company).order_by(Company.id)).all():
        products = db.scalar(
            select(func.count()).select_from(Product).where(Product.company_id == company.id)
        ) or 0
        emails = db.scalars(select(User.email).where(User.company_id == company.id).order_by(User.id)).all()
        rows.append(
            {
                "id": company.id,
                "name": company.name,
                "business_model": company.business_model,
                "products": products,
                "users": emails,
                "created_at": company.created_at,
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Regulations
# ---------------------------------------------------------------------------


@router.get("/regulations")
def list_regulations_admin(db: Session = Depends(get_db)):
    rows = []
    for regulation in db.scalars(select(Regulation).order_by(Regulation.id)).all():
        versions = db.scalar(
            select(func.count()).select_from(RegulationVersion).where(RegulationVersion.regulation_id == regulation.id)
        ) or 0
        legal_units = db.scalar(
            select(func.count())
            .select_from(LegalUnit)
            .join(RegulationVersion, LegalUnit.version_id == RegulationVersion.id)
            .where(RegulationVersion.regulation_id == regulation.id)
        ) or 0
        requirements = db.scalar(
            select(func.count()).select_from(Requirement).where(Requirement.regulation_id == regulation.id)
        ) or 0
        rows.append(
            {
                "id": regulation.id,
                "name": regulation.name,
                "short_name": regulation.short_name,
                "official_identifier": regulation.official_identifier,
                "jurisdiction": regulation.jurisdiction,
                "status": regulation.status,
                "versions": versions,
                "legal_units": legal_units,
                "requirements": requirements,
            }
        )
    return rows


@router.post("/regulations/reseed")
def reseed_regulations(db: Session = Depends(get_db)):
    """清空全局法规智能层并按种子数据恢复三部法规的初始状态。

    删除顺序遵循外键约束：先清引用 requirements/legal_units 的租户侧关联行
    （RESTRICT），再按 events/changes/runs/snapshots → sources → chunks →
    requirements → legal units → versions → regulations 的顺序自顶向下删除。
    """
    # 1. 租户侧对法规层的 RESTRICT 引用（链接行可删，发现本体保留证据快照）
    db.execute(delete(FeedbackCandidateRequirement))
    db.execute(delete(RemediationRequirement))
    db.execute(delete(RemediationEvidence))
    db.execute(delete(FindingRequirement))
    db.execute(delete(FindingEvidence))
    db.execute(update(TenantMissingContextItem).values(requirement_id=None))
    db.execute(update(AnalysisRun).values(regulation_id=None))
    # 2. 法规智能层本体
    db.execute(delete(RegulationEvent))
    db.execute(delete(RegulationChange))
    db.execute(delete(IngestionRun))
    db.execute(delete(SourceSnapshot))
    db.execute(delete(RegulatorySource))
    db.execute(text("DELETE FROM legal_chunks"))
    db.execute(delete(Requirement))
    db.execute(delete(LegalUnit))
    db.execute(delete(RegulationArticle))
    db.execute(delete(RegulationVersion))
    db.execute(delete(Regulation))
    db.commit()

    seeded = seed_regintel_if_empty(db)
    db.commit()

    # SQLite 本地向量索引常驻内存，按删除后的库全量重建
    rebuild_legal_chunk_store_from_db()
    rebuild_local_store_from_db()

    return {
        "reseeded": seeded,
        "regulations": _count(db, Regulation),
        "sources": _count(db, RegulatorySource),
        "versions": _count(db, RegulationVersion),
        "legal_units": _count(db, LegalUnit),
        "requirements": _count(db, Requirement),
        "chunks": _count(db, LegalChunk),
    }


# ---------------------------------------------------------------------------
# Demo data
# ---------------------------------------------------------------------------


@router.post("/demo/reset")
def reset_demo_data(db: Session = Depends(get_db)):
    """删除全部评估（business_model='evaluation'）工作区及其级联数据。"""
    company_ids = list(db.scalars(select(Company.id).where(Company.business_model == "evaluation")).all())
    if not company_ids:
        return {"deleted_companies": 0, "deleted_products": 0, "deleted_findings": 0, "deleted_sessions": 0}

    product_ids = list(db.scalars(select(Product.id).where(Product.company_id.in_(company_ids))).all())
    run_ids = list(db.scalars(select(TenantAgentRun.id).where(TenantAgentRun.tenant_id.in_(company_ids))).all())
    finding_ids = list(db.scalars(select(Finding.id).where(Finding.tenant_id.in_(company_ids))).all())
    remediation_ids = list(db.scalars(select(Remediation.id).where(Remediation.tenant_id.in_(company_ids))).all())
    feedback_ids = list(db.scalars(select(Feedback.id).where(Feedback.tenant_id.in_(company_ids))).all())
    analysis_run_ids = list(db.scalars(select(AnalysisRun.id).where(AnalysisRun.company_id.in_(company_ids))).all())
    session_count = db.scalar(
        select(func.count()).select_from(EvaluationSession).where(EvaluationSession.company_id.in_(company_ids))
    ) or 0

    # feedback / candidates（RESTRICT 引用 findings / remediations / twin / runs，最先删）
    if feedback_ids:
        candidate_ids = list(
            db.scalars(select(FeedbackCandidate.id).where(FeedbackCandidate.feedback_id.in_(feedback_ids))).all()
        )
        if candidate_ids:
            db.execute(delete(FeedbackCandidateRequirement).where(FeedbackCandidateRequirement.candidate_id.in_(candidate_ids)))
        db.execute(delete(FeedbackCandidate).where(FeedbackCandidate.feedback_id.in_(feedback_ids)))
        db.execute(delete(Feedback).where(Feedback.id.in_(feedback_ids)))
    # remediations
    if remediation_ids:
        db.execute(delete(RemediationRequirement).where(RemediationRequirement.remediation_id.in_(remediation_ids)))
        db.execute(delete(RemediationEvidence).where(RemediationEvidence.remediation_id.in_(remediation_ids)))
        db.execute(delete(Remediation).where(Remediation.id.in_(remediation_ids)))
    # findings
    if finding_ids:
        db.execute(delete(FindingRequirement).where(FindingRequirement.finding_id.in_(finding_ids)))
        db.execute(delete(FindingEvidence).where(FindingEvidence.finding_id.in_(finding_ids)))
        db.execute(delete(Finding).where(Finding.id.in_(finding_ids)))
    # tenant agent runs
    if run_ids:
        db.execute(delete(TenantMissingContextItem).where(TenantMissingContextItem.run_id.in_(run_ids)))
        db.execute(delete(TenantAgentRun).where(TenantAgentRun.id.in_(run_ids)))
    # legacy analysis runs
    if analysis_run_ids:
        db.execute(delete(ComplianceAction).where(ComplianceAction.run_id.in_(analysis_run_ids)))
        db.execute(delete(ImpactResult).where(ImpactResult.run_id.in_(analysis_run_ids)))
        db.execute(delete(AnalysisRun).where(AnalysisRun.id.in_(analysis_run_ids)))

    if product_ids:
        version_ids = list(
            db.scalars(select(ProductTwinVersion.id).where(ProductTwinVersion.product_id.in_(product_ids))).all()
        )
        fact_ids: list[int] = []
        if version_ids:
            fact_ids = list(
                db.scalars(select(ProductTwinFact.id).where(ProductTwinFact.version_id.in_(version_ids))).all()
            )
        # twin decisions → facts → versions → analysis refs（RESTRICT 由外向里）
        db.execute(delete(ProductTwinDecision).where(ProductTwinDecision.product_id.in_(product_ids)))
        if fact_ids:
            db.execute(delete(ProductTwinFact).where(ProductTwinFact.id.in_(fact_ids)))
        if version_ids:
            db.execute(delete(ProductTwinVersion).where(ProductTwinVersion.id.in_(version_ids)))
        db.execute(delete(ProductTwinAnalysisRef).where(ProductTwinAnalysisRef.product_id.in_(product_ids)))
        db.execute(delete(Assessment).where(Assessment.product_id.in_(product_ids)))
        db.execute(delete(SdkScan).where(SdkScan.product_id.in_(product_ids)))
        db.execute(delete(DeveloperIssue).where(DeveloperIssue.product_id.in_(product_ids)))

    db.execute(delete(EvaluationSession).where(EvaluationSession.company_id.in_(company_ids)))
    db.execute(delete(User).where(User.company_id.in_(company_ids)))
    if product_ids:
        db.execute(delete(Product).where(Product.id.in_(product_ids)))
    db.execute(delete(Company).where(Company.id.in_(company_ids)))
    db.commit()

    return {
        "deleted_companies": len(company_ids),
        "deleted_products": len(product_ids),
        "deleted_findings": len(finding_ids),
        "deleted_sessions": session_count,
    }


# ---------------------------------------------------------------------------
# System / RegIntel 运行状态
# ---------------------------------------------------------------------------


@router.get("/system")
def system_info():
    """后端运行时信息（版本 / 数据库 / LLM / 调度器 / 环境开关，均为非敏感字段）。"""
    from app.main import app as fastapi_app  # 延迟导入，避免与 main 的循环依赖

    settings = get_settings()
    return {
        "version": fastapi_app.version,
        "db_kind": db_kind(),
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "embedding_provider": settings.embedding_provider,
        "scheduler_enabled": settings.scheduler_enabled,
        "scheduler_interval_hours": settings.scheduler_interval_hours,
        "started_at": datetime.fromtimestamp(STARTED_AT, tz=timezone.utc).isoformat(),
        "uptime_seconds": round(time.time() - STARTED_AT, 3),
        "python_version": platform.python_version(),
        "env": {
            "desktop_mode": settings.desktop_mode,
            "legacy_tenant_api_enabled": settings.legacy_tenant_api_enabled,
            "evaluation_auth_bypass": settings.evaluation_auth_bypass,
            "run_seed": settings.run_seed,
            "mailer_provider": settings.mailer_provider,
        },
    }


def _ingestion_run_row(run: IngestionRun) -> dict:
    return {
        "id": run.id,
        "source_id": run.source_id,
        "regulation_id": run.regulation_id,
        "status": run.status,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "from_version_id": run.from_version_id,
        "to_version_id": run.to_version_id,
        "changes_count": run.changes_count,
        "requirements_count": run.requirements_count,
        "chunks_count": run.chunks_count,
        "error": run.error,
        "event_id": run.event_id,
    }


@router.get("/regintel/status")
def regintel_status(db: Session = Depends(get_db)):
    """法规智能层运行状态：来源列表 / 最近入库运行 / 事件计数 / 调度器状态。"""
    settings = get_settings()
    latest_runs = db.scalars(
        select(IngestionRun).order_by(IngestionRun.id.desc()).limit(10)
    ).all()
    latest_status_by_source: dict[int, str] = {}
    for run in db.scalars(select(IngestionRun).order_by(IngestionRun.id.desc())).all():
        if run.source_id is not None and run.source_id not in latest_status_by_source:
            latest_status_by_source[run.source_id] = run.status
    sources = [
        {
            "id": source.id,
            "name": source.source_name,
            "regulation_id": source.regulation_id,
            "jurisdiction": source.jurisdiction,
            "source_type": source.source_type,
            "enabled": source.is_active,
            "last_checked_at": source.last_checked_at,
            "last_success_at": source.last_success_at,
            "last_run_status": latest_status_by_source.get(source.id),
        }
        for source in db.scalars(select(RegulatorySource).order_by(RegulatorySource.priority)).all()
    ]
    return {
        "sources": sources,
        "recent_ingestion_runs": [_ingestion_run_row(run) for run in latest_runs],
        "events_count": _count(db, RegulationEvent),
        "scheduler": {
            "enabled": settings.scheduler_enabled,
            "interval_hours": settings.scheduler_interval_hours,
        },
    }


@router.post("/regintel/sources/{source_id}/ingest", status_code=201)
def ingest_source_admin(source_id: int, db: Session = Depends(get_db)):
    """触发一次来源抓取 + 入库流水线（复用 regintel 公共端点的同一逻辑）。"""
    from app.api.regintel import ingest_source

    return ingest_source(source_id, db)
