"""Structured contracts for requirement applicability analysis."""

from enum import Enum
from typing import Any, Literal

from pydantic import Field

from app.understanding.schemas import Confidence, Contract, FindingStatus


class DecisionSource(str, Enum):
    DETERMINISTIC = "DETERMINISTIC"
    LLM = "LLM"
    INSUFFICIENT_CONTEXT = "INSUFFICIENT_CONTEXT"


class ContextFact(Contract):
    """One Product Twin fact normalized for deterministic evaluation.

    ``complete`` means the value is an exhaustive statement for this field. It
    must be true before a non-match can prove non-applicability.
    """

    field_path: str = Field(min_length=1, max_length=200)
    value: Any = None
    status: FindingStatus
    confidence: Confidence
    confirmed: bool = False
    complete: bool = False
    fact_ids: list[int] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)


class ApplicabilityCondition(Contract):
    field_path: str = Field(min_length=1, max_length=200)
    operator: Literal["EQUALS", "IN", "CONTAINS_ANY", "IS_TRUE", "IS_FALSE"]
    value: Any = None
    question: str | None = Field(default=None, max_length=500)


class RequirementApplicabilityContext(Contract):
    requirement_id: int = Field(ge=1)
    jurisdiction: str | None = Field(default=None, max_length=100)
    subject_type: str | None = Field(default=None, max_length=200)
    product_types: list[str] = Field(default_factory=list)
    conditions: list[ApplicabilityCondition] = Field(default_factory=list)
    exceptions: list[ApplicabilityCondition] = Field(default_factory=list)
    required_fields: list[str] = Field(default_factory=list)


class ProductApplicabilityContext(Contract):
    facts: dict[str, ContextFact] = Field(default_factory=dict)


class MatchedFact(Contract):
    field: str
    value: Any = None
    fact_ids: list[int] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)


class MissingContextItem(Contract):
    field_path: str = Field(min_length=1, max_length=200)
    question: str = Field(min_length=1, max_length=500)
    reason: str = Field(min_length=1, max_length=1000)
    requirement_id: int | None = Field(default=None, ge=1)


class ApplicabilityResult(Contract):
    requirement_id: int = Field(ge=1)
    applies: bool | None
    confidence: Confidence
    matched_facts: list[MatchedFact] = Field(default_factory=list)
    missing_context: list[MissingContextItem] = Field(default_factory=list)
    reasoning_summary: str = Field(min_length=1, max_length=2000)
    decision_source: DecisionSource
