"""Strict contracts for human-confirmed feedback processing."""
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import Field, model_validator

from app.understanding.schemas import Confidence, Contract, FindingStatus


class FeedbackType(str, Enum):
    FACT_CORRECTION = "FACT_CORRECTION"
    FINDING_FEEDBACK = "FINDING_FEEDBACK"
    REMEDIATION_FEEDBACK = "REMEDIATION_FEEDBACK"


class CandidateStatus(str, Enum):
    PROPOSED = "PROPOSED"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    APPLIED = "APPLIED"


class RemediationNegativeReason(str, Enum):
    INCORRECT = "INCORRECT"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    TOO_GENERIC = "TOO_GENERIC"
    MISSING_CONTEXT = "MISSING_CONTEXT"
    UNSAFE = "UNSAFE"
    OTHER = "OTHER"


class FeedbackCreateRequest(Contract):
    tenant_id: int = Field(ge=1)
    product_id: int = Field(ge=1)
    feedback_type: FeedbackType
    raw_text: str = Field(min_length=1, max_length=10000)
    finding_id: int | None = Field(default=None, ge=1)
    remediation_id: int | None = Field(default=None, ge=1)
    created_by: str = Field(default="", max_length=200)
    useful: bool | None = None
    negative_reason: RemediationNegativeReason | None = None

    @model_validator(mode="after")
    def validate_target(self):
        if self.finding_id is None and self.remediation_id is None and self.feedback_type != FeedbackType.FACT_CORRECTION:
            raise ValueError("finding_id or remediation_id is required")
        if self.feedback_type == FeedbackType.REMEDIATION_FEEDBACK and self.remediation_id is None:
            raise ValueError("remediation_id is required for REMEDIATION_FEEDBACK")
        if self.useful is True and self.negative_reason is not None:
            raise ValueError("useful feedback cannot include a negative reason")
        return self


class FactCorrectionProposal(Contract):
    candidate_type: FeedbackType = FeedbackType.FACT_CORRECTION
    target_fact_id: int | None = Field(default=None, ge=1)
    proposed_name: str | None = Field(default=None, min_length=1, max_length=200)
    proposed_value: Any = None
    # Product Twin observations use FindingStatus; CONFIRMED is a review state,
    # not an observation status.
    proposed_status: FindingStatus | None = None
    confidence: Confidence
    reasoning_summary: str = Field(min_length=1, max_length=4000)
    needs_clarification: bool = False
    clarification_question: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_clarification(self):
        if self.needs_clarification and not self.clarification_question:
            raise ValueError("a discriminating clarification question is required")
        if not self.needs_clarification and (not self.proposed_name or self.proposed_status is None):
            raise ValueError("a resolved proposal requires name and Product Twin status")
        return self


class ClarificationRequest(Contract):
    tenant_id: int = Field(ge=1)
    answer: str = Field(min_length=1, max_length=4000)


class CandidateDecisionRequest(Contract):
    tenant_id: int = Field(ge=1)
    note: str = Field(default="", max_length=2000)


class FeedbackRecord(Contract):
    id: int
    tenant_id: int
    product_id: int
    finding_id: int | None = None
    remediation_id: int | None = None
    feedback_type: FeedbackType
    raw_text: str
    created_by: str
    useful: bool | None = None
    negative_reason: RemediationNegativeReason | None = None
    created_at: datetime


class CandidateRecord(Contract):
    id: int
    feedback_id: int
    tenant_id: int
    product_id: int
    candidate_type: FeedbackType
    status: CandidateStatus
    target_fact_id: int | None = None
    proposed_name: str | None = None
    proposed_value: Any = None
    proposed_status: FindingStatus | None = None
    reasoning_summary: str
    confidence: Confidence
    clarification_question: str | None = None
    clarification_answer: str | None = None
    applied_fact_id: int | None = None
    applied_twin_version_id: int | None = None
    reanalysis_run_id: int | None = None
    last_error: str = ""
    requirement_ids: list[int] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class FeedbackSubmission(Contract):
    feedback: FeedbackRecord
    candidates: list[CandidateRecord] = Field(default_factory=list)


class CandidateTransitionError(ValueError):
    pass


_TRANSITIONS = {
    CandidateStatus.PROPOSED: {CandidateStatus.NEEDS_CLARIFICATION, CandidateStatus.CONFIRMED, CandidateStatus.REJECTED},
    CandidateStatus.NEEDS_CLARIFICATION: {CandidateStatus.PROPOSED, CandidateStatus.REJECTED},
    CandidateStatus.CONFIRMED: {CandidateStatus.APPLIED},
    CandidateStatus.REJECTED: set(),
    CandidateStatus.APPLIED: set(),
}


def validate_candidate_transition(current: CandidateStatus, target: CandidateStatus) -> None:
    if current == target:
        return
    if target not in _TRANSITIONS[current]:
        raise CandidateTransitionError(f"Illegal candidate transition {current.value} -> {target.value}")
