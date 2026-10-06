"""Structured contracts for requirement-to-control gap analysis."""

from enum import Enum
from typing import Any, Literal

from pydantic import Field, model_validator

from app.understanding.schemas import Confidence, Contract, FindingStatus


class GapStatus(str, Enum):
    CONFIRMED = "CONFIRMED"
    POTENTIAL = "POTENTIAL"
    NO_GAP = "NO_GAP"
    UNKNOWN = "UNKNOWN"


class GapType(str, Enum):
    MISSING_CONTROL = "MISSING_CONTROL"
    PARTIAL_CONTROL = "PARTIAL_CONTROL"
    OUTDATED_DOCUMENT = "OUTDATED_DOCUMENT"
    INCORRECT_CONFIGURATION = "INCORRECT_CONFIGURATION"
    MISSING_PROCESS = "MISSING_PROCESS"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    UNKNOWN = "UNKNOWN"


class RequirementControlContext(Contract):
    requirement_id: int = Field(ge=1)
    required_control: str = Field(min_length=1, max_length=200)
    required_state: str = Field(min_length=1, max_length=2000)
    affected_assets: list[str] = Field(default_factory=list)


class ControlObservation(Contract):
    """A Product Twin observation relevant to a required control.

    ``explicit_absence`` is a separate affirmative assertion. It cannot be
    inferred from NOT_DETECTED and requires confirmed user evidence.
    """

    control: str = Field(min_length=1, max_length=200)
    status: FindingStatus
    confidence: Confidence
    source_kind: str = Field(min_length=1, max_length=30)
    confirmation_status: Literal["UNREVIEWED", "CONFIRMED", "CORRECTED"] = "UNREVIEWED"
    explicit_absence: bool = False
    current_state: str = Field(default="", max_length=2000)
    affected_assets: list[str] = Field(default_factory=list)
    fact_ids: list[int] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_explicit_absence(self):
        if self.explicit_absence and (
            self.source_kind != "USER"
            or self.confirmation_status != "CONFIRMED"
            or self.status != FindingStatus.PRESENT
            or not self.evidence
        ):
            raise ValueError(
                "explicit_absence requires a confirmed PRESENT user assertion with evidence"
            )
        return self


class GapAnalysisResult(Contract):
    requirement_id: int = Field(ge=1)
    gap_status: GapStatus
    gap_type: GapType
    current_state: str = Field(min_length=1, max_length=2000)
    required_state: str = Field(min_length=1, max_length=2000)
    affected_assets: list[str] = Field(default_factory=list)
    confidence: Confidence
    reasoning_summary: str = Field(min_length=1, max_length=2000)
    supporting_fact_ids: list[int] = Field(default_factory=list)
    supporting_evidence: list[dict[str, Any]] = Field(default_factory=list)
