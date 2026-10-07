from app.tenant.feedback.schemas import CandidateStatus, validate_candidate_transition, CandidateTransitionError
import pytest
def test_confirmed_can_apply_but_applied_is_terminal():
    validate_candidate_transition(CandidateStatus.CONFIRMED,CandidateStatus.APPLIED)
    with pytest.raises(CandidateTransitionError): validate_candidate_transition(CandidateStatus.APPLIED,CandidateStatus.CONFIRMED)
