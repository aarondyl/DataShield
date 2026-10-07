"""Tenant-scoped Finding list and canonical trace detail APIs."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.evaluation_auth import CurrentPrincipal, require_company_access, require_principal, require_product_access
from app.tenant.applicability.schemas import ApplicabilityResult, MissingContextItem
from app.tenant.context.ownership import (
    ProductNotFoundError,
    TenantNotFoundError,
    TenantProductMismatchError,
)
from app.tenant.findings.schemas import (
    FindingEvidenceRecord,
    FindingListItem,
    FindingRecord,
    TenantAgentRunRecord,
)
from app.tenant.findings.service import list_findings, load_finding
from app.tenant.gap.schemas import GapAnalysisResult
from app.tenant.regulatory.schemas import LegalEvidence, RequirementContext
from app.understanding.schemas import Contract

router = APIRouter(prefix="/v1/findings", tags=["Tenant Intelligence Findings"])


class FindingDetailResponse(Contract):
    finding: FindingRecord
    agent_run: TenantAgentRunRecord
    requirements: list[RequirementContext] = Field(default_factory=list)
    legal_evidence: list[LegalEvidence] = Field(default_factory=list)
    evidence_snapshots: list[FindingEvidenceRecord] = Field(default_factory=list)
    applicability: list[ApplicabilityResult] = Field(default_factory=list)
    gap: list[GapAnalysisResult] = Field(default_factory=list)
    missing_context: list[MissingContextItem] = Field(default_factory=list)
    product_twin_version: dict[str, Any] | None = None


@router.get("", response_model=list[FindingListItem])
def get_findings(
    tenant_id: int = Query(ge=1),
    product_id: int | None = Query(default=None, ge=1),
    status: str | None = Query(default=None, pattern="^(OPEN|DISMISSED|RESOLVED)$"),
    db: Session = Depends(get_db),
    principal: CurrentPrincipal = Depends(require_principal),
) -> list[FindingListItem]:
    require_company_access(tenant_id, principal)
    if product_id is not None:
        require_product_access(db, product_id, principal)
    try:
        return list_findings(db, tenant_id, product_id=product_id, status=status)
    except (TenantNotFoundError, ProductNotFoundError, TenantProductMismatchError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{finding_id}", response_model=FindingDetailResponse)
def get_finding(
    finding_id: int,
    tenant_id: int = Query(ge=1),
    db: Session = Depends(get_db),
    principal: CurrentPrincipal = Depends(require_principal),
) -> FindingDetailResponse:
    require_company_access(tenant_id, principal)
    detail = load_finding(db, tenant_id, finding_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Finding does not exist for this tenant")
    output = detail.run.output or {}
    twin = None
    if detail.finding.product_twin_version_id is not None:
        twin = {
            "id": detail.finding.product_twin_version_id,
            "version_number": detail.run.input_snapshot.get("product_context", {}).get(
                "product_twin_version_number"
            ),
        }
    return FindingDetailResponse(
        finding=detail.finding,
        agent_run=detail.run,
        requirements=detail.requirements,
        legal_evidence=detail.legal_evidence,
        evidence_snapshots=detail.evidence_snapshots,
        applicability=output.get("applicability_results", []),
        gap=output.get("gap_results", []),
        missing_context=output.get("missing_context", []),
        product_twin_version=twin,
    )
