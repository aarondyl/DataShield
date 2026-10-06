"""Synchronous manual entrypoint for the Tenant Intelligence state machine."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.tenant.agent.graph import get_tenant_graph
from app.tenant.agent.schemas import TenantAnalyzeRequest, TenantAnalyzeResponse
from app.tenant.agent.state import TenantAgentState
from app.tenant.context.ownership import (
    ProductNotFoundError,
    TenantNotFoundError,
    TenantProductMismatchError,
)
from app.tenant.findings.schemas import TenantTriggerType
from app.tenant.findings.service import (
    create_pending_agent_run,
    mark_run_failed,
)
from app.tenant.regulatory.service import (
    InvalidRegulationTriggerError,
    RegulationTriggerNotFoundError,
    TriggerDataConflictError,
    UnsupportedRegulationEventError,
)

router = APIRouter(prefix="/v1/tenant-agent", tags=["Tenant Intelligence"])


def _deduplicate_questions(items):
    return list({item.field_path: item for item in items}.values())


@router.post("/analyze", response_model=TenantAnalyzeResponse, status_code=201)
def analyze(payload: TenantAnalyzeRequest, db: Session = Depends(get_db)) -> TenantAnalyzeResponse:
    settings = get_settings()
    try:
        run = create_pending_agent_run(
            db,
            tenant_id=payload.tenant_id,
            product_id=payload.product_id,
            trigger_type=TenantTriggerType(payload.trigger_type),
            trigger_id=payload.trigger_id,
            model_provider=settings.llm_provider,
            model_name=settings.llm_model if settings.llm_provider == "api" else "deterministic/mock",
            prompt_version="tenant-applicability-v1",
        )
    except (TenantNotFoundError, ProductNotFoundError, TenantProductMismatchError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    initial: TenantAgentState = {
        "tenant_id": payload.tenant_id,
        "product_id": payload.product_id,
        "trigger_type": payload.trigger_type,
        "trigger_id": payload.trigger_id,
        "regulation_id": payload.regulation_id,
        "requirement_ids": payload.requirement_ids,
        "query": payload.query,
        "run_id": run.id,
        "requirements": [],
        "ready_requirement_ids": [],
        "legal_evidence": [],
        "missing_context": [],
        "applicability_results": [],
        "gap_results": [],
        "finding_candidates": [],
        "finding_ids": [],
        "status": "PENDING",
        "errors": [],
    }
    try:
        result = get_tenant_graph().invoke(initial)
    except RegulationTriggerNotFoundError as exc:
        mark_run_failed(db, run.id, str(exc))
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (
        UnsupportedRegulationEventError,
        TriggerDataConflictError,
        InvalidRegulationTriggerError,
    ) as exc:
        mark_run_failed(db, run.id, str(exc))
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        mark_run_failed(db, run.id, str(exc))
        raise HTTPException(status_code=500, detail="Tenant Intelligence workflow failed") from exc

    return TenantAnalyzeResponse(
        run_id=run.id,
        status=result["status"],
        finding_ids=result.get("finding_ids", []),
        missing_context=_deduplicate_questions(result.get("missing_context", [])),
    )
