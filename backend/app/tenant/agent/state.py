"""Stable DTO-only state passed between Tenant Intelligence graph nodes."""

from typing import TypedDict

from app.tenant.applicability.schemas import ApplicabilityResult, MissingContextItem
from app.tenant.context.schemas import ProductContext
from app.tenant.findings.schemas import FindingCandidate
from app.tenant.gap.schemas import GapAnalysisResult
from app.tenant.regulatory.schemas import (
    LegalEvidence,
    ManualScanContext,
    RegulationTrigger,
    RequirementContext,
)


class TenantAgentState(TypedDict, total=False):
    tenant_id: int
    product_id: int
    trigger_type: str
    trigger_id: str | None
    regulation_id: int | None
    requirement_ids: list[int]
    query: str
    run_id: int | None
    product_context: ProductContext | None
    product_twin_version_id: int | None
    regulation_trigger: RegulationTrigger | None
    manual_scan: ManualScanContext | None
    requirements: list[RequirementContext]
    ready_requirement_ids: list[int]
    legal_evidence: list[LegalEvidence]
    missing_context: list[MissingContextItem]
    applicability_results: list[ApplicabilityResult]
    gap_results: list[GapAnalysisResult]
    finding_candidates: list[FindingCandidate]
    finding_ids: list[int]
    status: str
    errors: list[str]
