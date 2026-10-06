"""Stable persistence and query contracts for Tenant Intelligence findings."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import Field

from app.tenant.applicability.schemas import ApplicabilityResult, MissingContextItem
from app.tenant.context.schemas import ProductContext
from app.tenant.gap.schemas import GapAnalysisResult
from app.tenant.regulatory.schemas import LegalEvidence, RegulationTrigger, RequirementContext
from app.understanding.schemas import Confidence, Contract


class TenantAgentRunStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    NEEDS_USER_INPUT = "NEEDS_USER_INPUT"
    FAILED = "FAILED"


class TenantTriggerType(str, Enum):
    REGULATION_CHANGE = "REGULATION_CHANGE"
    MANUAL_SCAN = "MANUAL_SCAN"
    USER_REQUEST = "USER_REQUEST"
    PRODUCT_CONTEXT_CHANGE = "PRODUCT_CONTEXT_CHANGE"
    FEEDBACK_REANALYSIS = "FEEDBACK_REANALYSIS"


class ImpactLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class FindingRecordStatus(str, Enum):
    OPEN = "OPEN"
    DISMISSED = "DISMISSED"
    RESOLVED = "RESOLVED"


class TenantAgentInputSnapshot(Contract):
    tenant_id: int = Field(ge=1)
    product_id: int = Field(ge=1)
    product_twin_version_id: int | None = None
    product_context: ProductContext
    trigger: RegulationTrigger
    requirements: list[RequirementContext] = Field(default_factory=list)
    legal_evidence: list[LegalEvidence] = Field(default_factory=list)


class TenantAgentOutputSnapshot(Contract):
    applicability_results: list[ApplicabilityResult] = Field(default_factory=list)
    gap_results: list[GapAnalysisResult] = Field(default_factory=list)
    finding_ids: list[int] = Field(default_factory=list)
    missing_context: list[MissingContextItem] = Field(default_factory=list)
    status: TenantAgentRunStatus


class FindingCandidate(Contract):
    title: str = Field(min_length=1, max_length=300)
    impact_level: ImpactLevel
    confidence: Confidence
    applicability: ApplicabilityResult
    gap: GapAnalysisResult | None = None
    requirements: list[RequirementContext] = Field(default_factory=list)
    legal_evidence: list[LegalEvidence] = Field(default_factory=list)
    product_twin_version_id: int | None = None


class FindingRecord(Contract):
    id: int
    run_id: int
    tenant_id: int
    product_id: int
    trigger_type: str
    trigger_id: str | None = None
    title: str
    status: FindingRecordStatus
    impact_level: ImpactLevel
    confidence: Confidence
    applicability_summary: str
    gap_status: str
    gap_type: str
    gap_summary: str
    product_twin_version_id: int | None = None
    created_at: datetime
    updated_at: datetime


class FindingListItem(FindingRecord):
    requirement_count: int = 0
    evidence_count: int = 0


class TenantAgentRunRecord(Contract):
    id: int
    tenant_id: int
    product_id: int
    trigger_type: str
    trigger_id: str | None = None
    status: TenantAgentRunStatus
    model_provider: str
    model_name: str
    prompt_version: str
    input_snapshot: dict[str, Any]
    output: dict[str, Any]
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str
    created_at: datetime


class EvidenceSnapshot(Contract):
    regulation_id: int
    regulation_name: str
    version_id: int
    version: int
    legal_unit_id: int
    article: str
    heading: str
    content: str
    source_url: str
    effective_date: datetime | None = None
    requirement_ids: list[int] = Field(default_factory=list)


class FindingEvidenceRecord(Contract):
    id: int
    finding_id: int
    legal_unit_id: int
    requirement_id: int | None = None
    snapshot: EvidenceSnapshot
    created_at: datetime


class FindingDetail(Contract):
    finding: FindingRecord
    run: TenantAgentRunRecord
    requirements: list[RequirementContext] = Field(default_factory=list)
    legal_evidence: list[LegalEvidence] = Field(default_factory=list)
    evidence_snapshots: list[FindingEvidenceRecord] = Field(default_factory=list)
