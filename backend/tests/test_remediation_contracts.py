"""Unit coverage for grounded remediation contracts and prompt rendering."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from app.tenant.context.schemas import ProductFactContext
from app.tenant.applicability.schemas import ApplicabilityResult, DecisionSource
from app.tenant.findings.schemas import FindingRecord, FindingRecordStatus, ImpactLevel
from app.tenant.gap.schemas import GapAnalysisResult, GapStatus, GapType
from app.tenant.regulatory.schemas import LegalEvidence, RequirementContext
from app.tenant.remediation import (
    CodeChangePlan,
    CodeChangeProposal,
    CodeTestInstruction,
    DocumentChangePlan,
    ProposedDocumentChange,
    RemediationCreateRequest,
    RemediationDecisionRequest,
    RemediationEvidenceReference,
    RemediationGroundingError,
    RemediationInputSnapshot,
    RemediationPlanningInput,
    RemediationRecord,
    RemediationStatus,
    RemediationType,
    RequestedCodeChange,
    build_authoritative_problem_fields,
    build_code_change_plan,
    render_coding_prompt,
    validate_remediation_grounding,
)
from app.understanding.schemas import FindingStatus


def requirement(requirement_id: int = 7, legal_unit_id: int = 11) -> RequirementContext:
    return RequirementContext(
        id=requirement_id,
        regulation_id=3,
        version_id=5,
        legal_unit_id=legal_unit_id,
        requirement_type="OBLIGATION",
        subject_type="PROVIDER",
        action_type="PROVIDE",
        object_type="ACCOUNT_DELETION",
        conditions=[],
        exceptions=[],
        summary="Provide an effective account deletion mechanism.",
        confidence=0.94,
        status="VALIDATED",
        regulation_name="Example Regulation",
        jurisdiction="EU",
        regulation_version=2,
        source_url="https://regulator.example/law",
    )


def legal_evidence(requirement_id: int = 7, legal_unit_id: int = 11) -> LegalEvidence:
    return LegalEvidence(
        legal_unit_id=legal_unit_id,
        regulation_id=3,
        regulation_name="Example Regulation",
        version_id=5,
        version=2,
        article="Article 17",
        heading="Right to erasure",
        content="A data subject may request erasure under the stated conditions.",
        source_url="https://regulator.example/law#17",
        requirement_ids=[requirement_id],
    )


def product_fact() -> ProductFactContext:
    return ProductFactContext(
        fact_id=19,
        group="controls",
        name="account_deletion",
        status=FindingStatus.NOT_DETECTED,
        source="REPOSITORY",
        confidence=0.72,
        evidence=[{"file": "routes/account.py", "reason": "Selected repository evidence"}],
        scan_scope={"analysis_mode": "SELECTED_PATHS"},
        review_status="UNREVIEWED",
    )


def planning_input(
    remediation_type: RemediationType = RemediationType.CODE_CHANGE,
) -> RemediationPlanningInput:
    request = RemediationCreateRequest(
        tenant_id=1,
        remediation_type=remediation_type,
        document_type="PRIVACY_POLICY" if remediation_type == RemediationType.DOCUMENT_CHANGE else None,
        target_components=["account deletion"],
        constraints=["Preserve the existing API contract"],
    )
    return RemediationPlanningInput(
        finding_id=23,
        tenant_id=1,
        product_id=2,
        finding_title="Account deletion capability may be insufficient",
        impact_level=ImpactLevel.HIGH,
        finding_confidence=0.72,
        applicability_summary="The product serves users in the covered market.",
        gap_status="POTENTIAL",
        gap_type="INSUFFICIENT_EVIDENCE",
        gap_summary="The selected scan did not detect an account deletion control.",
        gap_current_state="No account deletion control was detected in the selected scan scope.",
        gap_required_state="Users must have an effective account deletion mechanism.",
        product_twin_version_id=13,
        requirements=[requirement()],
        legal_evidence=[legal_evidence()],
        relevant_product_facts=[product_fact()],
        planner_request=request,
    )


def code_proposal() -> CodeChangeProposal:
    return CodeChangeProposal(
        requested_changes=[
            RequestedCodeChange(
                target="account deletion component",
                change="Add a user-initiated deletion flow with auditable completion.",
                rationale="Address the persisted Finding without assuming an unverified path.",
            )
        ],
        affected_files_or_components=["account deletion component"],
        constraints=["Preserve the existing API contract"],
        acceptance_criteria=["An authenticated user can request account deletion."],
        tests=[
            CodeTestInstruction(
                name="account deletion request",
                purpose="Verify the requested deletion flow.",
                expected_result="The request completes and records the outcome.",
            )
        ],
        do_not_modify=["unrelated authentication behavior"],
    )


def evidence_reference(requirement_id: int = 7, legal_unit_id: int = 11):
    return RemediationEvidenceReference(
        requirement_id=requirement_id,
        legal_unit_id=legal_unit_id,
        regulation_id=3,
        regulation_name="Example Regulation",
        version_id=5,
        version=2,
        article="Article 17",
        heading="Right to erasure",
        source_url="https://regulator.example/law#17",
    )


def document_plan(reference: RemediationEvidenceReference | None = None) -> DocumentChangePlan:
    return DocumentChangePlan(
        document_type="PRIVACY_POLICY",
        issue="The deletion process is not described.",
        current_state="The current notice does not describe the deletion request process.",
        required_state="The notice must explain the effective deletion mechanism.",
        proposed_changes=[
            ProposedDocumentChange(
                section="Your rights",
                change="Add the account deletion request process.",
                rationale="Reflect the requirement and the persisted Finding.",
            )
        ],
        draft_text="Draft: Users may request account deletion through the verified process.",
        evidence=[reference or evidence_reference()],
        acceptance_criteria=["A human reviewer verifies the draft against product behavior."],
    )


def remediation_snapshot(context: RemediationPlanningInput) -> RemediationInputSnapshot:
    now = datetime(2026, 1, 1)
    applicability = ApplicabilityResult(
        requirement_id=7,
        applies=True,
        confidence=.9,
        reasoning_summary=context.applicability_summary,
        decision_source=DecisionSource.DETERMINISTIC,
    )
    gap = GapAnalysisResult(
        requirement_id=7,
        gap_status=GapStatus.POTENTIAL,
        gap_type=GapType.INSUFFICIENT_EVIDENCE,
        current_state=context.gap_current_state,
        required_state=context.gap_required_state,
        confidence=.72,
        reasoning_summary=context.gap_summary,
    )
    return RemediationInputSnapshot(
        finding=FindingRecord(
            id=context.finding_id,
            run_id=4,
            tenant_id=context.tenant_id,
            product_id=context.product_id,
            trigger_type="MANUAL_SCAN",
            title=context.finding_title,
            status=FindingRecordStatus.OPEN,
            impact_level=context.impact_level,
            confidence=context.finding_confidence,
            applicability_summary=context.applicability_summary,
            gap_status=context.gap_status,
            gap_type=context.gap_type,
            gap_summary=context.gap_summary,
            product_twin_version_id=context.product_twin_version_id,
            created_at=now,
            updated_at=now,
        ),
        applicability_result=applicability,
        gap_result=gap,
        requirements=context.requirements,
        legal_evidence=context.legal_evidence,
        relevant_product_facts=context.relevant_product_facts,
        planner_request=context.planner_request,
        product_twin_version_id=context.product_twin_version_id,
    )


def test_code_change_complete_schema():
    plan = build_code_change_plan(planning_input(), code_proposal())
    assert isinstance(plan, CodeChangePlan)
    assert plan.problem == "Account deletion capability may be insufficient"
    assert plan.requested_changes[0].target == "account deletion component"


def test_document_change_complete_schema():
    plan = document_plan()
    assert plan.document_type == "PRIVACY_POLICY"
    assert plan.evidence[0].legal_unit_id == 11


@pytest.mark.parametrize(
    ("contract", "payload"),
    [
        (RemediationDecisionRequest, {"tenant_id": 1, "unexpected": True}),
        (
            RemediationCreateRequest,
            {"tenant_id": 1, "remediation_type": "CODE_CHANGE", "unknown": "value"},
        ),
    ],
)
def test_unknown_fields_are_rejected(contract, payload):
    with pytest.raises(ValidationError):
        contract.model_validate(payload)


def test_invalid_remediation_type_is_rejected():
    with pytest.raises(ValidationError):
        RemediationCreateRequest(tenant_id=1, remediation_type="CONFIG_CHANGE")


def test_invalid_status_is_rejected():
    with pytest.raises(ValueError):
        RemediationStatus("COMPLETED")


@pytest.mark.parametrize(
    "update",
    [
        {"finding_id": 0},
        {"finding_confidence": 1.01},
        {"product_twin_version_id": 0},
    ],
)
def test_planning_input_validates_ids_and_confidence(update):
    payload = planning_input().model_dump()
    payload.update(update)
    with pytest.raises(ValidationError):
        RemediationPlanningInput.model_validate(payload)


def test_document_text_is_explicitly_a_human_review_draft():
    plan = document_plan()
    assert plan.draft_status == "DRAFT_REQUIRES_HUMAN_REVIEW"
    with pytest.raises(ValidationError):
        DocumentChangePlan.model_validate(
            {**plan.model_dump(), "draft_status": "FINAL_APPROVED"}
        )


def test_evidence_reference_contract_requires_canonical_ids():
    reference = evidence_reference()
    assert reference.requirement_id == 7
    with pytest.raises(ValidationError):
        RemediationEvidenceReference.model_validate(
            {**reference.model_dump(), "legal_unit_id": 0}
        )


def test_grounding_rejects_requirement_outside_finding():
    plan = document_plan(evidence_reference(requirement_id=99))
    with pytest.raises(RemediationGroundingError, match="requirements outside"):
        validate_remediation_grounding(plan, {7}, {11})


def test_grounding_rejects_legal_unit_outside_finding():
    plan = document_plan(evidence_reference(legal_unit_id=99))
    with pytest.raises(RemediationGroundingError, match="legal units outside"):
        validate_remediation_grounding(plan, {7}, {11})


def test_grounding_accepts_finding_evidence_subset():
    validate_remediation_grounding(document_plan(), {7, 8}, {11, 12})


def test_renderer_contains_finding_requirement_and_evidence():
    prompt = render_coding_prompt(planning_input(), code_proposal())
    assert "Finding ID: 23" in prompt
    assert "Requirement 7" in prompt
    assert "Legal unit 11" in prompt
    assert "Article 17" in prompt


def test_renderer_contains_acceptance_criteria():
    prompt = render_coding_prompt(planning_input(), code_proposal())
    assert "# Acceptance Criteria" in prompt
    assert "An authenticated user can request account deletion." in prompt


def test_renderer_contains_tests():
    prompt = render_coding_prompt(planning_input(), code_proposal())
    assert "# Tests" in prompt
    assert "Expected result: The request completes and records the outcome." in prompt


def test_renderer_contains_do_not_modify():
    prompt = render_coding_prompt(planning_input(), code_proposal())
    assert "# Do Not Modify" in prompt
    assert "unrelated authentication behavior" in prompt


def test_renderer_does_not_invent_file_paths():
    prompt = render_coding_prompt(planning_input(), code_proposal())
    assert "account deletion component" in prompt
    assert "src/auth/delete.ts" not in prompt


def test_renderer_is_deterministic_for_identical_input():
    context = planning_input()
    proposal = code_proposal()
    assert render_coding_prompt(context, proposal) == render_coding_prompt(context, proposal)


def test_authoritative_fields_are_copied_from_finding_and_gap():
    context = planning_input()
    fields = build_authoritative_problem_fields(context)
    plan = build_code_change_plan(context, code_proposal())
    assert fields.problem == context.finding_title == plan.problem
    assert fields.current_state == context.gap_current_state == plan.current_state
    assert fields.required_state == context.gap_required_state == plan.required_state


def test_coding_prompt_renderer_has_no_llm_dependency(monkeypatch):
    def fail_if_called():
        raise AssertionError("LLM must not be called by the renderer")

    monkeypatch.setattr("app.core.llm.get_llm_client", fail_if_called)
    plan = build_code_change_plan(planning_input(), code_proposal())
    assert "# Execution Instructions" in plan.coding_prompt


def test_approved_means_accepted_recommendation_without_execution_state():
    now = datetime(2026, 1, 1)
    context = planning_input()
    record = RemediationRecord(
        id=1,
        finding_id=context.finding_id,
        tenant_id=context.tenant_id,
        product_id=context.product_id,
        remediation_type=RemediationType.CODE_CHANGE,
        status=RemediationStatus.APPROVED,
        title="Implement account deletion",
        summary="Approved recommendation; execution is outside this contract.",
        plan=build_code_change_plan(context, code_proposal()),
        input_snapshot=remediation_snapshot(context),
        product_twin_version_id=context.product_twin_version_id,
        decision_note="Recommendation reviewed",
        decided_at=now,
        created_at=now,
        updated_at=now,
    )
    payload = record.model_dump(mode="json")
    assert payload["status"] == "APPROVED"
    assert "execution_status" not in payload
    assert "finding_status" not in payload


def test_create_request_requires_document_type_only_for_document_changes():
    with pytest.raises(ValidationError, match="document_type is required"):
        RemediationCreateRequest(tenant_id=1, remediation_type="DOCUMENT_CHANGE")
    with pytest.raises(ValidationError, match="only valid"):
        RemediationCreateRequest(
            tenant_id=1,
            remediation_type="CODE_CHANGE",
            document_type="PRIVACY_POLICY",
        )


def test_planning_input_rejects_cross_tenant_request():
    payload = planning_input().model_dump()
    payload["planner_request"]["tenant_id"] = 2
    with pytest.raises(ValidationError, match="does not match"):
        RemediationPlanningInput.model_validate(payload)


def test_planning_input_rejects_evidence_for_unknown_requirement():
    payload = planning_input().model_dump()
    payload["legal_evidence"][0]["requirement_ids"] = [999]
    with pytest.raises(ValidationError, match="outside the planning input"):
        RemediationPlanningInput.model_validate(payload)
