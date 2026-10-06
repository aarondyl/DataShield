"""Strict contracts for grounded remediation proposals.

Finding data remains the factual record. These contracts describe a proposed
response to that record. Persisted planning inputs and plans are immutable;
approval and rejection only change decision metadata in the future persistence
layer.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Literal

from pydantic import Field, model_validator

from app.tenant.context.schemas import ProductFactContext
from app.tenant.applicability.schemas import ApplicabilityResult
from app.tenant.findings.schemas import FindingRecord, ImpactLevel
from app.tenant.gap.schemas import GapAnalysisResult
from app.tenant.regulatory.schemas import LegalEvidence, RequirementContext
from app.understanding.schemas import Confidence, Contract


class RemediationType(str, Enum):
    CODE_CHANGE = "CODE_CHANGE"
    DOCUMENT_CHANGE = "DOCUMENT_CHANGE"


class RemediationStatus(str, Enum):
    PROPOSED = "PROPOSED"
    # APPROVED means that the recommendation was accepted. It does not mean
    # that code/document changes were executed or that the Finding is resolved.
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class RemediationCreateRequest(Contract):
    """Tenant-scoped planning request; it cannot add legal authorities."""

    tenant_id: int = Field(ge=1)
    remediation_type: RemediationType
    document_type: str | None = Field(default=None, min_length=1, max_length=100)
    target_components: list[str] = Field(default_factory=list, max_length=100)
    constraints: list[str] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def validate_type_specific_fields(self):
        if self.remediation_type == RemediationType.DOCUMENT_CHANGE and not self.document_type:
            raise ValueError("document_type is required for DOCUMENT_CHANGE")
        if self.remediation_type == RemediationType.CODE_CHANGE and self.document_type is not None:
            raise ValueError("document_type is only valid for DOCUMENT_CHANGE")
        return self


class RemediationDecisionRequest(Contract):
    """The endpoint determines APPROVED or REJECTED; callers cannot set status."""

    tenant_id: int = Field(ge=1)
    note: str | None = Field(default=None, max_length=2000)


class RemediationEvidenceReference(Contract):
    """Canonical legal reference copied from a Finding's allowed trace."""

    requirement_id: int = Field(ge=1)
    legal_unit_id: int = Field(ge=1)
    regulation_id: int = Field(ge=1)
    regulation_name: str = Field(min_length=1, max_length=300)
    version_id: int = Field(ge=1)
    version: int = Field(ge=1)
    article: str = Field(default="", max_length=100)
    heading: str = Field(default="", max_length=500)
    source_url: str = Field(default="", max_length=2000)


class RemediationPlanningInput(Contract):
    """Minimum trusted Finding context supplied to a future planner.

    ``relevant_product_facts`` is an explicitly selected subset of the Product
    Twin snapshot used by the Finding. The full TenantAgentRun snapshot is not
    accepted by this contract.
    """

    finding_id: int = Field(ge=1)
    tenant_id: int = Field(ge=1)
    product_id: int = Field(ge=1)
    finding_title: str = Field(min_length=1, max_length=300)
    impact_level: ImpactLevel
    finding_confidence: Confidence
    applicability_summary: str = Field(min_length=1, max_length=4000)
    gap_status: str = Field(min_length=1, max_length=20)
    gap_type: str = Field(min_length=1, max_length=40)
    gap_summary: str = Field(min_length=1, max_length=4000)
    gap_current_state: str = Field(min_length=1, max_length=4000)
    gap_required_state: str = Field(min_length=1, max_length=4000)
    product_twin_version_id: int | None = Field(default=None, ge=1)
    requirements: list[RequirementContext] = Field(min_length=1)
    legal_evidence: list[LegalEvidence] = Field(min_length=1)
    relevant_product_facts: list[ProductFactContext] = Field(default_factory=list)
    planner_request: RemediationCreateRequest

    @model_validator(mode="after")
    def validate_request_scope(self):
        if self.planner_request.tenant_id != self.tenant_id:
            raise ValueError("planner_request tenant_id does not match the Finding tenant")
        requirement_ids = {item.id for item in self.requirements}
        for evidence in self.legal_evidence:
            unknown = set(evidence.requirement_ids) - requirement_ids
            if unknown:
                raise ValueError(
                    f"legal evidence references requirements outside the planning input: {sorted(unknown)}"
                )
        return self


class AuthoritativeProblemFields(Contract):
    """Fact fields copied from Finding/Gap input, never authored by an LLM."""

    problem: str = Field(min_length=1, max_length=4000)
    current_state: str = Field(min_length=1, max_length=4000)
    required_state: str = Field(min_length=1, max_length=4000)


class RemediationInputSnapshot(Contract):
    """Minimal immutable input actually used to produce a remediation plan."""

    finding: FindingRecord
    applicability_result: ApplicabilityResult
    gap_result: GapAnalysisResult
    requirements: list[RequirementContext] = Field(min_length=1)
    legal_evidence: list[LegalEvidence] = Field(min_length=1)
    relevant_product_facts: list[ProductFactContext] = Field(default_factory=list)
    planner_request: RemediationCreateRequest
    product_twin_version_id: int | None = Field(default=None, ge=1)


class RequestedCodeChange(Contract):
    target: str = Field(min_length=1, max_length=500)
    change: str = Field(min_length=1, max_length=4000)
    rationale: str = Field(min_length=1, max_length=4000)


class CodeTestInstruction(Contract):
    name: str = Field(min_length=1, max_length=300)
    purpose: str = Field(min_length=1, max_length=2000)
    expected_result: str = Field(min_length=1, max_length=2000)


class CodeChangeProposal(Contract):
    """Planner-editable fields before authoritative fields and prompt are added."""

    requested_changes: list[RequestedCodeChange] = Field(min_length=1, max_length=100)
    affected_files_or_components: list[str] = Field(min_length=1, max_length=100)
    constraints: list[str] = Field(default_factory=list, max_length=100)
    acceptance_criteria: list[str] = Field(min_length=1, max_length=100)
    tests: list[CodeTestInstruction] = Field(min_length=1, max_length=100)
    do_not_modify: list[str] = Field(default_factory=list, max_length=100)


class CodeChangePlan(AuthoritativeProblemFields, CodeChangeProposal):
    """Immutable proposed code change. ``coding_prompt`` is renderer-owned."""

    coding_prompt: str = Field(min_length=1, max_length=50000)


class ProposedDocumentChange(Contract):
    section: str = Field(min_length=1, max_length=500)
    change: str = Field(min_length=1, max_length=4000)
    rationale: str = Field(min_length=1, max_length=4000)


class DocumentChangePlan(Contract):
    """A draft recommendation. It is never an approved or applied document."""

    document_type: str = Field(min_length=1, max_length=100)
    issue: str = Field(min_length=1, max_length=4000)
    current_state: str = Field(min_length=1, max_length=4000)
    required_state: str = Field(min_length=1, max_length=4000)
    proposed_changes: list[ProposedDocumentChange] = Field(min_length=1, max_length=100)
    draft_text: str = Field(min_length=1, max_length=50000)
    draft_status: Literal["DRAFT_REQUIRES_HUMAN_REVIEW"] = "DRAFT_REQUIRES_HUMAN_REVIEW"
    evidence: list[RemediationEvidenceReference] = Field(min_length=1)
    acceptance_criteria: list[str] = Field(min_length=1, max_length=100)


RemediationPlan = Annotated[CodeChangePlan | DocumentChangePlan, Field(union_mode="left_to_right")]


class RemediationRecord(Contract):
    """Stored plan payload is immutable; only decision metadata changes later."""

    id: int = Field(ge=1)
    finding_id: int = Field(ge=1)
    tenant_id: int = Field(ge=1)
    product_id: int = Field(ge=1)
    remediation_type: RemediationType
    status: RemediationStatus
    title: str = Field(min_length=1, max_length=300)
    summary: str = Field(min_length=1, max_length=4000)
    plan: RemediationPlan
    input_snapshot: RemediationInputSnapshot
    product_twin_version_id: int | None = Field(default=None, ge=1)
    model_provider: str = Field(default="", max_length=50)
    model_name: str = Field(default="", max_length=100)
    prompt_version: str = Field(default="", max_length=50)
    decision_note: str | None = Field(default=None, max_length=2000)
    decided_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def validate_plan_type(self):
        expected = (
            CodeChangePlan
            if self.remediation_type == RemediationType.CODE_CHANGE
            else DocumentChangePlan
        )
        if not isinstance(self.plan, expected):
            raise ValueError("plan payload does not match remediation_type")
        return self


class RemediationListItem(Contract):
    id: int = Field(ge=1)
    finding_id: int = Field(ge=1)
    tenant_id: int = Field(ge=1)
    product_id: int = Field(ge=1)
    remediation_type: RemediationType
    status: RemediationStatus
    title: str
    summary: str
    product_twin_version_id: int | None = Field(default=None, ge=1)
    created_at: datetime
    updated_at: datetime


class RemediationDetail(Contract):
    remediation: RemediationRecord
    finding: FindingRecord
    requirements: list[RequirementContext] = Field(default_factory=list)
    legal_evidence: list[LegalEvidence] = Field(default_factory=list)
    evidence_references: list[RemediationEvidenceReference] = Field(default_factory=list)
    product_twin_version: "RemediationProductTwinVersionReference | None" = None


class RemediationProductTwinVersionReference(Contract):
    id: int = Field(ge=1)
    version_number: int = Field(ge=1)


class RemediationGroundingError(ValueError):
    """Raised when a plan cites canonical entities not linked to its Finding."""


def validate_remediation_grounding(
    plan: CodeChangePlan | DocumentChangePlan,
    allowed_requirement_ids: set[int] | list[int] | tuple[int, ...],
    allowed_legal_unit_ids: set[int] | list[int] | tuple[int, ...],
) -> None:
    """Reject, rather than remove, references outside the Finding trace."""

    references = plan.evidence if isinstance(plan, DocumentChangePlan) else []
    allowed_requirements = set(allowed_requirement_ids)
    allowed_units = set(allowed_legal_unit_ids)
    unknown_requirements = sorted(
        {item.requirement_id for item in references} - allowed_requirements
    )
    if unknown_requirements:
        raise RemediationGroundingError(
            f"Remediation references requirements outside the Finding: {unknown_requirements}"
        )
    unknown_units = sorted({item.legal_unit_id for item in references} - allowed_units)
    if unknown_units:
        raise RemediationGroundingError(
            f"Remediation references legal units outside the Finding: {unknown_units}"
        )
