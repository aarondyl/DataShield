"""Applicability contracts and deterministic pre-checks."""

from app.tenant.applicability.schemas import (
    ApplicabilityCondition,
    ApplicabilityResult,
    ContextFact,
    DecisionSource,
    MatchedFact,
    MissingContextItem,
    ProductApplicabilityContext,
    RequirementApplicabilityContext,
)
from app.tenant.applicability.service import deterministic_applicability_precheck

__all__ = [
    "ApplicabilityCondition",
    "ApplicabilityResult",
    "ContextFact",
    "DecisionSource",
    "MatchedFact",
    "MissingContextItem",
    "ProductApplicabilityContext",
    "RequirementApplicabilityContext",
    "deterministic_applicability_precheck",
]
