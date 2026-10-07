"""Deterministic gap semantics preserve UNKNOWN and NOT_DETECTED."""

import pytest
from pydantic import ValidationError

from app.tenant.gap import (
    ControlObservation,
    GapStatus,
    GapType,
    RequirementControlContext,
    deterministic_gap_analysis,
)


REQUIREMENT = RequirementControlContext(
    requirement_id=20,
    required_control="ai_disclosure",
    required_state="Applicable AI transparency information must be provided.",
    affected_assets=["website.chat"],
)


def _observation(status, **overrides):
    values = {
        "control": "ai_disclosure",
        "status": status,
        "confidence": .84,
        "source_kind": "WEBSITE",
        "fact_ids": [7],
        "evidence": [{"type": "WEB_PAGE", "url": "https://example.com", "reason": "scan"}],
    }
    values.update(overrides)
    return ControlObservation(**values)


def test_present_control_has_no_gap():
    result = deterministic_gap_analysis(REQUIREMENT, [_observation("PRESENT")])

    assert result.gap_status == GapStatus.NO_GAP
    assert result.gap_type == GapType.UNKNOWN
    assert result.supporting_fact_ids == [7]


def test_not_detected_is_only_a_potential_gap():
    result = deterministic_gap_analysis(REQUIREMENT, [_observation("NOT_DETECTED")])

    assert result.gap_status == GapStatus.POTENTIAL
    assert result.gap_type == GapType.INSUFFICIENT_EVIDENCE
    assert "不能证明" in result.reasoning_summary


def test_unknown_context_is_not_a_missing_control():
    result = deterministic_gap_analysis(REQUIREMENT, [_observation("UNKNOWN")])

    assert result.gap_status == GapStatus.UNKNOWN
    assert result.gap_type == GapType.UNKNOWN
    assert result.confidence == 0


def test_partial_control_is_a_potential_partial_gap():
    result = deterministic_gap_analysis(REQUIREMENT, [_observation("PARTIAL")])

    assert result.gap_status == GapStatus.POTENTIAL
    assert result.gap_type == GapType.PARTIAL_CONTROL


def test_confirmed_affirmative_absence_is_a_confirmed_gap():
    absence = _observation(
        "PRESENT",
        source_kind="USER",
        confirmation_status="CONFIRMED",
        explicit_absence=True,
        current_state="Product owner confirmed that no AI disclosure exists.",
    )

    result = deterministic_gap_analysis(REQUIREMENT, [absence])

    assert result.gap_status == GapStatus.CONFIRMED
    assert result.gap_type == GapType.MISSING_CONTROL


def test_not_detected_cannot_be_marked_as_explicit_absence():
    with pytest.raises(ValidationError):
        _observation(
            "NOT_DETECTED",
            source_kind="USER",
            confirmation_status="CONFIRMED",
            explicit_absence=True,
        )


def test_conflicting_present_and_absent_facts_remain_unknown():
    present = _observation("PRESENT")
    absence = _observation(
        "PRESENT",
        source_kind="USER",
        confirmation_status="CONFIRMED",
        explicit_absence=True,
    )

    result = deterministic_gap_analysis(REQUIREMENT, [present, absence])

    assert result.gap_status == GapStatus.UNKNOWN
    assert "冲突" in result.reasoning_summary
