"""Tenant-scoped APIs for planning and reviewing remediation proposals."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.evaluation_auth import CurrentPrincipal, require_company_access, require_principal, validate_browser_origin
from app.core.llm import MockLLMClient
from app.tenant.remediation import (
    RemediationConflictError,
    RemediationCreateRequest,
    RemediationDecisionRequest,
    RemediationDetail,
    RemediationGroundingError,
    RemediationListItem,
    RemediationNotFoundError,
    RemediationPersistenceError,
    RemediationPlanningError,
    RemediationProviderError,
    approve_remediation,
    get_remediation,
    list_remediations_for_finding,
    plan_remediation,
    reject_remediation,
)

router = APIRouter(prefix="/v1", tags=["Tenant Intelligence Remediations"], dependencies=[Depends(validate_browser_origin)])


def _domain_error(exc: Exception) -> HTTPException:
    if isinstance(exc, RemediationNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, RemediationConflictError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, RemediationProviderError):
        return HTTPException(status_code=502, detail=str(exc))
    if isinstance(exc, (RemediationGroundingError, RemediationPlanningError)):
        return HTTPException(status_code=422, detail=str(exc))
    # Integrity failures in persisted canonical context are server-side failures.
    if isinstance(exc, RemediationPersistenceError):
        return HTTPException(status_code=500, detail="Remediation canonical context is invalid")
    return HTTPException(status_code=500, detail="Remediation operation failed")


@router.post(
    "/findings/{finding_id}/remediations",
    response_model=RemediationDetail,
    status_code=status.HTTP_201_CREATED,
)
def create_finding_remediation(
    finding_id: int,
    request: RemediationCreateRequest,
    db: Session = Depends(get_db),
    principal: CurrentPrincipal = Depends(require_principal),
) -> RemediationDetail:
    require_company_access(request.tenant_id, principal)
    try:
        return plan_remediation(db, request.tenant_id, finding_id, request, llm_client=MockLLMClient() if principal.edition == "demo" else None)
    except (
        RemediationNotFoundError,
        RemediationConflictError,
        RemediationProviderError,
        RemediationGroundingError,
        RemediationPlanningError,
        RemediationPersistenceError,
    ) as exc:
        raise _domain_error(exc) from exc


@router.get(
    "/findings/{finding_id}/remediations",
    response_model=list[RemediationListItem],
)
def list_finding_remediations(
    finding_id: int,
    tenant_id: int = Query(ge=1),
    db: Session = Depends(get_db),
    principal: CurrentPrincipal = Depends(require_principal),
) -> list[RemediationListItem]:
    require_company_access(tenant_id, principal)
    try:
        return list_remediations_for_finding(db, tenant_id, finding_id)
    except (RemediationNotFoundError, RemediationPersistenceError) as exc:
        raise _domain_error(exc) from exc


@router.get("/remediations/{remediation_id}", response_model=RemediationDetail)
def remediation_detail(
    remediation_id: int,
    tenant_id: int = Query(ge=1),
    db: Session = Depends(get_db),
    principal: CurrentPrincipal = Depends(require_principal),
) -> RemediationDetail:
    require_company_access(tenant_id, principal)
    try:
        return get_remediation(db, tenant_id, remediation_id)
    except (RemediationNotFoundError, RemediationPersistenceError) as exc:
        raise _domain_error(exc) from exc


def _decide(
    remediation_id: int,
    request: RemediationDecisionRequest,
    db: Session,
    *,
    approve: bool,
) -> RemediationDetail:
    try:
        operation = approve_remediation if approve else reject_remediation
        operation(db, request.tenant_id, remediation_id, note=request.note)
        return get_remediation(db, request.tenant_id, remediation_id)
    except (
        RemediationNotFoundError,
        RemediationConflictError,
        RemediationPersistenceError,
    ) as exc:
        raise _domain_error(exc) from exc


@router.post("/remediations/{remediation_id}/approve", response_model=RemediationDetail)
def approve(
    remediation_id: int,
    request: RemediationDecisionRequest,
    db: Session = Depends(get_db),
    principal: CurrentPrincipal = Depends(require_principal),
) -> RemediationDetail:
    require_company_access(request.tenant_id, principal)
    return _decide(remediation_id, request, db, approve=True)


@router.post("/remediations/{remediation_id}/reject", response_model=RemediationDetail)
def reject(
    remediation_id: int,
    request: RemediationDecisionRequest,
    db: Session = Depends(get_db),
    principal: CurrentPrincipal = Depends(require_principal),
) -> RemediationDetail:
    require_company_access(request.tenant_id, principal)
    return _decide(remediation_id, request, db, approve=False)
