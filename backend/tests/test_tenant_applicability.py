"""Deterministic applicability checks before any LLM reasoning."""

import pytest
from pydantic import ValidationError

from app.tenant.applicability import (
    ApplicabilityCondition,
    ContextFact,
    DecisionSource,
    ProductApplicabilityContext,
    RequirementApplicabilityContext,
    deterministic_applicability_precheck,
)


def _fact(field, value, *, status="PRESENT", confirmed=True, complete=True, confidence=.9):
    return ContextFact(field_path=field, value=value, status=status, confidence=confidence,
                       confirmed=confirmed, complete=complete, fact_ids=[1],
                       evidence=[{"type": "USER_DESCRIPTION", "reason": "confirmed"}])


def test_eu_market_and_matching_data_requirement_is_applicable():
    requirement = RequirementApplicabilityContext(
        requirement_id=10,
        jurisdiction="EU",
        conditions=[ApplicabilityCondition(
            field_path="data_types", operator="CONTAINS_ANY", value=["personal_data"]
        )],
    )
    product = ProductApplicabilityContext(facts={
        "markets": _fact("markets", ["Germany"]),
        "data_types": _fact("data_types", ["personal_data", "email"]),
    })

    result = deterministic_applicability_precheck(requirement, product)

    assert result is not None
    assert result.applies is True
    assert result.decision_source == DecisionSource.DETERMINISTIC
    assert {item.field for item in result.matched_facts} == {"markets", "data_types"}


def test_confirmed_complete_non_eu_market_is_non_applicable():
    requirement = RequirementApplicabilityContext(requirement_id=11, jurisdiction="EU")
    product = ProductApplicabilityContext(facts={"markets": _fact("markets", ["CN"])})

    result = deterministic_applicability_precheck(requirement, product)

    assert result is not None and result.applies is False
    assert result.confidence == .9


@pytest.mark.parametrize("status", ["UNKNOWN", "NOT_DETECTED"])
def test_unknown_or_not_detected_context_requests_user_input(status):
    requirement = RequirementApplicabilityContext(
        requirement_id=12,
        jurisdiction="EU",
        required_fields=["data_types.biometric"],
    )
    product = ProductApplicabilityContext(facts={
        "markets": _fact("markets", ["EU"]),
        "data_types.biometric": _fact("data_types.biometric", None, status=status),
    })

    result = deterministic_applicability_precheck(requirement, product)

    assert result is not None and result.applies is None
    assert result.decision_source == DecisionSource.INSUFFICIENT_CONTEXT
    assert result.missing_context[0].field_path == "data_types.biometric"
    assert "依赖此事实" in result.missing_context[0].reason


def test_partial_non_match_cannot_prove_non_applicability():
    requirement = RequirementApplicabilityContext(requirement_id=13, jurisdiction="EU")
    product = ProductApplicabilityContext(facts={
        "markets": _fact("markets", ["CN"], status="PARTIAL", confirmed=False, complete=False),
    })

    result = deterministic_applicability_precheck(requirement, product)

    assert result is not None and result.applies is None
    assert result.missing_context[0].field_path == "markets"


def test_matching_exception_makes_requirement_non_applicable():
    requirement = RequirementApplicabilityContext(
        requirement_id=14,
        jurisdiction="EU",
        exceptions=[ApplicabilityCondition(field_path="business_model", operator="EQUALS", value="household")],
    )
    product = ProductApplicabilityContext(facts={
        "markets": _fact("markets", ["EU"]),
        "business_model": _fact("business_model", "household"),
    })

    result = deterministic_applicability_precheck(requirement, product)

    assert result is not None and result.applies is False
    assert "例外条件" in result.reasoning_summary


def test_contracts_reject_extra_fields_and_invalid_confidence():
    with pytest.raises(ValidationError):
        ContextFact(field_path="markets", value=["EU"], status="PRESENT", confidence=1.1)
    with pytest.raises(ValidationError):
        RequirementApplicabilityContext(requirement_id=1, unexpected=True)
