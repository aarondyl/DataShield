import pytest
from pydantic import ValidationError

from app.tenant.feedback.schemas import (
    CandidateStatus, CandidateTransitionError, FactCorrectionProposal,
    FeedbackCreateRequest, FeedbackType, validate_candidate_transition,
)


def test_fact_proposal_uses_product_twin_observation_status():
    p = FactCorrectionProposal(proposed_name="account_deletion", proposed_status="PRESENT",
        proposed_value=True, confidence=.8, reasoning_summary="User reports it is available.")
    assert p.proposed_status.value == "PRESENT"
    with pytest.raises(ValidationError):
        FactCorrectionProposal(proposed_name="x", proposed_status="CONFIRMED", confidence=.8,
            reasoning_summary="bad")


def test_ambiguous_proposal_requires_question():
    p = FactCorrectionProposal(confidence=.3, reasoning_summary="Ambiguous", needs_clarification=True,
        clarification_question="Is this available in production?")
    assert p.needs_clarification
    with pytest.raises(ValidationError):
        FactCorrectionProposal(confidence=.3, reasoning_summary="Ambiguous", needs_clarification=True)


def test_feedback_contract_is_strict_and_targeted():
    # 产品事实纠正允许不绑定具体发现/整改（产品画像页直接纠正）
    FeedbackCreateRequest(tenant_id=1, product_id=1, feedback_type="FACT_CORRECTION", raw_text="x")
    with pytest.raises(ValidationError):
        FeedbackCreateRequest(tenant_id=1, product_id=1, feedback_type="FINDING_FEEDBACK", raw_text="x")
    with pytest.raises(ValidationError):
        FeedbackCreateRequest(tenant_id=1, product_id=1, finding_id=1,
            feedback_type="FACT_CORRECTION", raw_text="x", surprise=True)


@pytest.mark.parametrize("current,target", [
    ("PROPOSED", "NEEDS_CLARIFICATION"), ("NEEDS_CLARIFICATION", "PROPOSED"),
    ("PROPOSED", "CONFIRMED"), ("PROPOSED", "REJECTED"), ("CONFIRMED", "APPLIED"),
])
def test_legal_transitions(current, target):
    validate_candidate_transition(CandidateStatus(current), CandidateStatus(target))


@pytest.mark.parametrize("current,target", [
    ("NEEDS_CLARIFICATION", "CONFIRMED"), ("APPLIED", "PROPOSED"),
    ("REJECTED", "CONFIRMED"), ("CONFIRMED", "REJECTED"),
])
def test_illegal_transitions(current, target):
    with pytest.raises(CandidateTransitionError):
        validate_candidate_transition(CandidateStatus(current), CandidateStatus(target))
