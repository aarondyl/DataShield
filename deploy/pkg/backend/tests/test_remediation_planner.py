"""Grounded Remediation planner behavior without HTTP or real model calls."""

import json

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.core.llm import MockLLMClient
from app.db.base import Base
from app.models import (
    Company,
    Finding,
    FindingEvidence,
    FindingRequirement,
    LegalUnit,
    Product,
    ProductTwinFact,
    ProductTwinVersion,
    Regulation,
    RegulationVersion,
    Remediation,
    Requirement,
    TenantAgentRun,
)
from app.tenant.applicability.schemas import ApplicabilityResult, DecisionSource
from app.tenant.context.schemas import ProductContext, ProductFactContext
from app.tenant.findings.schemas import TenantAgentInputSnapshot
from app.tenant.gap.schemas import GapAnalysisResult, GapStatus, GapType
from app.tenant.regulatory.schemas import LegalEvidence, ManualScanContext, RequirementContext
from app.tenant.remediation import (
    RemediationConflictError,
    RemediationCreateRequest,
    RemediationGroundingError,
    RemediationNotFoundError,
    RemediationPlanningError,
    RemediationType,
    plan_remediation,
)


class StaticClient:
    provider_name = "test"
    model_name = "structured-test"

    def __init__(self, payload=None, error=None):
        self.payload = payload
        self.error = error
        self.calls = []

    def chat_json(self, system_prompt, user_prompt, *, context=None):
        self.calls.append((system_prompt, user_prompt, context))
        if self.error:
            raise self.error
        return self.payload


@pytest.fixture
def planner_db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'planner.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([Company(id=1, name="Tenant A"), Company(id=2, name="Tenant B")])
        db.flush()
        db.add_all([
            Product(id=1, company_id=1, name="Product A"),
            Product(id=2, company_id=2, name="Product B"),
        ])
        regulation = Regulation(
            id=1,
            name="Example AI Act",
            jurisdiction="EU",
            canonical_source_url="https://regulator.example/ai-act",
        )
        db.add(regulation)
        db.flush()
        version = RegulationVersion(
            id=1,
            regulation_id=1,
            version_number=1,
            normalized_text="Article 50 transparency",
            content_hash="a" * 64,
            is_current=True,
        )
        db.add(version)
        db.flush()
        regulation.current_version_id = version.id
        unit = LegalUnit(
            id=1,
            version_id=1,
            unit_type="article",
            unit_number="Article 50",
            heading="AI transparency",
            text="Providers shall disclose interaction with an AI system.",
        )
        db.add(unit)
        db.flush()
        db.add(Requirement(
            id=1,
            regulation_id=1,
            version_id=1,
            legal_unit_id=1,
            requirement_type="obligation",
            subject_type="provider",
            action_type="inform",
            object_type="AI system",
            conditions_json=[],
            exceptions_json=[],
            summary="Provide AI transparency disclosure",
            confidence=.9,
            status="ACTIVE",
        ))
        old_twin = ProductTwinVersion(id=1, product_id=1, version_number=1, reason="finding")
        current_twin = ProductTwinVersion(id=2, product_id=1, version_number=2, reason="later")
        db.add_all([old_twin, current_twin])
        db.flush()
        db.add(ProductTwinFact(
            version_id=2,
            group_name="controls",
            name="ai_disclosure",
            status="PRESENT",
            confidence=1,
            source_kind="USER",
            evidence=[{"file": "backend/current_only.py", "reason": "later fact"}],
            scan_scope={},
            confirmation_status="CONFIRMED",
        ))
        db.commit()
        yield db


def _requirement():
    return RequirementContext(
        id=1,
        regulation_id=1,
        version_id=1,
        legal_unit_id=1,
        requirement_type="obligation",
        subject_type="provider",
        action_type="inform",
        object_type="AI system",
        conditions=[],
        exceptions=[],
        summary="Provide AI transparency disclosure",
        confidence=.9,
        status="ACTIVE",
        regulation_name="Example AI Act",
        jurisdiction="EU",
        regulation_version=1,
        source_url="https://regulator.example/ai-act",
    )


def _evidence():
    return LegalEvidence(
        legal_unit_id=1,
        regulation_id=1,
        regulation_name="Example AI Act",
        version_id=1,
        version=1,
        article="Article 50",
        heading="AI transparency",
        content="Providers shall disclose interaction with an AI system.",
        source_url="https://regulator.example/ai-act",
        requirement_ids=[1],
    )


def _historical_facts():
    return [
        ProductFactContext(
            fact_id=10,
            group="controls",
            name="ai_disclosure",
            status="NOT_DETECTED",
            source="REPOSITORY",
            confidence=.8,
            evidence=[{"file": "frontend/src/AiChat.tsx", "reason": "selected scan"}],
            scan_scope={"analysis_mode": "SELECTED_PATHS"},
            review_status="UNREVIEWED",
        ),
        ProductFactContext(
            fact_id=11,
            group="features",
            name="AI_chat",
            status="PRESENT",
            source="REPOSITORY",
            confidence=.9,
            evidence=[{"file": "frontend/src/AiChat.tsx", "reason": "AI interaction"}],
            scan_scope={},
            review_status="CONFIRMED",
        ),
        ProductFactContext(
            fact_id=12,
            group="vendors",
            name="Stripe",
            status="PRESENT",
            source="REPOSITORY",
            confidence=.9,
            evidence=[{"file": "backend/payment.py", "reason": "payment vendor"}],
            scan_scope={},
            review_status="UNREVIEWED",
        ),
        ProductFactContext(
            fact_id=13,
            group="public_documents",
            name="ai_disclosure_details",
            status="UNKNOWN",
            source="WEBSITE",
            confidence=0,
            evidence=[],
            scan_scope={"pages": ["/"]},
            review_status="UNREVIEWED",
        ),
    ]


def _scenario(db, *, finding_status="OPEN", gap_status=GapStatus.POTENTIAL):
    requirement = _requirement()
    evidence = _evidence()
    applicability = ApplicabilityResult(
        requirement_id=1,
        applies=True,
        confidence=.9,
        reasoning_summary="The product provides an AI service in the covered market.",
        decision_source=DecisionSource.DETERMINISTIC,
    )
    confirmed = gap_status == GapStatus.CONFIRMED
    gap = GapAnalysisResult(
        requirement_id=1,
        gap_status=gap_status,
        gap_type=(GapType.MISSING_CONTROL if confirmed else GapType.INSUFFICIENT_EVIDENCE),
        current_state=(
            "The user confirmed that the disclosure control is absent."
            if confirmed else "The selected scan did not detect an AI disclosure control."
        ),
        required_state="Provide AI transparency disclosure.",
        affected_assets=["AI chat"],
        confidence=.8,
        reasoning_summary=(
            "Confirmed product evidence shows the control is absent."
            if confirmed else "NOT_DETECTED indicates a potential gap requiring verification."
        ),
        supporting_fact_ids=[10],
    )
    context = ProductContext(
        tenant_id=1,
        product_id=1,
        product_twin_version_id=1,
        product_twin_version_number=1,
        facts=_historical_facts(),
    )
    input_snapshot = TenantAgentInputSnapshot(
        tenant_id=1,
        product_id=1,
        product_twin_version_id=1,
        product_context=context,
        trigger=ManualScanContext(requirement_ids=[1]),
        requirements=[requirement],
        legal_evidence=[evidence],
    )
    run = TenantAgentRun(
        tenant_id=1,
        product_id=1,
        trigger_type="MANUAL_SCAN",
        status="COMPLETED",
        model_provider="mock",
        model_name="deterministic",
        prompt_version="tenant-applicability-v1",
        input_snapshot_json=input_snapshot.model_dump(mode="json"),
        output_json={
            "applicability_results": [applicability.model_dump(mode="json")],
            "gap_results": [gap.model_dump(mode="json")],
            "finding_ids": [],
            "missing_context": [],
            "status": "COMPLETED",
        },
        error="",
    )
    db.add(run)
    db.flush()
    finding = Finding(
        run_id=run.id,
        tenant_id=1,
        product_id=1,
        trigger_type="MANUAL_SCAN",
        title="AI transparency disclosure may be missing",
        status=finding_status,
        impact_level="HIGH",
        confidence=.8,
        applicability_summary=applicability.reasoning_summary,
        gap_status=gap.gap_status.value,
        gap_type=gap.gap_type.value,
        gap_summary=gap.reasoning_summary,
        product_twin_version_id=1,
    )
    db.add(finding)
    db.flush()
    run.output_json = {**run.output_json, "finding_ids": [finding.id]}
    db.add(FindingRequirement(finding_id=finding.id, requirement_id=1))
    db.add(FindingEvidence(
        finding_id=finding.id,
        legal_unit_id=1,
        requirement_id=1,
        evidence_snapshot_json=evidence.model_dump(mode="json"),
    ))
    db.commit()
    return finding


def _request(remediation_type=RemediationType.CODE_CHANGE):
    return RemediationCreateRequest(
        tenant_id=1,
        remediation_type=remediation_type,
        document_type=("PRIVACY_POLICY" if remediation_type == RemediationType.DOCUMENT_CHANGE else None),
        target_components=["AI chat component"],
        constraints=["Preserve existing chat behavior"],
    )


def _reference(**updates):
    value = {
        "requirement_id": 1,
        "legal_unit_id": 1,
        "regulation_id": 1,
        "regulation_name": "Example AI Act",
        "version_id": 1,
        "version": 1,
        "article": "Article 50",
        "heading": "AI transparency",
        "source_url": "https://regulator.example/ai-act",
    }
    value.update(updates)
    return value


def _code_payload(target="AI chat component", **extra):
    value = {
        "requested_changes": [{
            "target": target,
            "change": "Verify whether the potential gap exists, then add the required disclosure.",
            "rationale": "Address the potential gap without treating NOT_DETECTED as absence.",
        }],
        "affected_files_or_components": [target],
        "constraints": ["Preserve existing chat behavior"],
        "acceptance_criteria": ["The verified disclosure behavior satisfies the supplied requirement."],
        "tests": [{
            "name": "AI disclosure",
            "purpose": "Verify disclosure behavior.",
            "expected_result": "The disclosure appears before AI interaction.",
        }],
        "do_not_modify": ["Unrelated behavior"],
    }
    value.update(extra)
    return value


def _document_payload(*, reference=None, draft=None, **extra):
    value = {
        "document_type": "PRIVACY_POLICY",
        "proposed_changes": [{
            "section": "AI transparency",
            "change": "Add a potential-gap disclosure draft for human review.",
            "rationale": "Preserve uncertainty while addressing the Finding.",
        }],
        "draft_text": draft or "DRAFT — REQUIRES HUMAN REVIEW. [TO CONFIRM: product details]",
        "draft_status": "DRAFT_REQUIRES_HUMAN_REVIEW",
        "evidence": [reference or _reference()],
        "acceptance_criteria": ["A human reviewer confirms every product statement."],
    }
    value.update(extra)
    return value


@pytest.mark.parametrize("remediation_type", [RemediationType.CODE_CHANGE, RemediationType.DOCUMENT_CHANGE])
def test_planner_happy_paths(planner_db, remediation_type):
    finding = _scenario(planner_db)
    detail = plan_remediation(planner_db, 1, finding.id, _request(remediation_type))
    assert detail.remediation.remediation_type == remediation_type
    assert detail.requirements[0].id == 1
    assert detail.legal_evidence[0].legal_unit_id == 1


@pytest.mark.parametrize("status", ["DISMISSED", "RESOLVED"])
def test_only_open_finding_can_be_planned(planner_db, status):
    finding = _scenario(planner_db, finding_status=status)
    with pytest.raises(RemediationConflictError, match=status):
        plan_remediation(planner_db, 1, finding.id, _request())


def test_tenant_ownership_is_enforced(planner_db):
    finding = _scenario(planner_db)
    request = _request().model_copy(update={"tenant_id": 2})
    with pytest.raises(RemediationNotFoundError):
        plan_remediation(planner_db, 2, finding.id, request)


def test_planner_uses_historical_context_not_current_twin(planner_db):
    finding = _scenario(planner_db)
    detail = plan_remediation(planner_db, 1, finding.id, _request())
    snapshot = detail.remediation.input_snapshot
    assert snapshot.product_twin_version_id == 1
    serialized = json.dumps(snapshot.model_dump(mode="json"))
    assert "frontend/src/AiChat.tsx" in serialized
    assert "backend/current_only.py" not in serialized


def test_relevant_fact_selection_excludes_unrelated_vendor(planner_db):
    finding = _scenario(planner_db)
    detail = plan_remediation(planner_db, 1, finding.id, _request())
    names = {item.name for item in detail.remediation.input_snapshot.relevant_product_facts}
    assert {"ai_disclosure", "AI_chat"} <= names
    assert "Stripe" not in names


def test_code_llm_contract_rejects_authoritative_fields(planner_db):
    finding = _scenario(planner_db)
    client = StaticClient(_code_payload(problem="invented"))
    with pytest.raises(RemediationPlanningError, match="schema validation"):
        plan_remediation(planner_db, 1, finding.id, _request(), llm_client=client)


def test_authoritative_fields_are_injected_after_llm(planner_db):
    finding = _scenario(planner_db)
    detail = plan_remediation(
        planner_db, 1, finding.id, _request(), llm_client=StaticClient(_code_payload())
    )
    plan = detail.remediation.plan
    gap = detail.remediation.input_snapshot.gap_result
    assert plan.problem == finding.title
    assert plan.current_state == gap.current_state
    assert plan.required_state == gap.required_state


def test_coding_prompt_is_renderer_owned_and_deterministic(planner_db):
    finding = _scenario(planner_db)
    first = plan_remediation(
        planner_db, 1, finding.id, _request(), llm_client=StaticClient(_code_payload())
    )
    second = plan_remediation(
        planner_db, 1, finding.id, _request(), llm_client=StaticClient(_code_payload())
    )
    assert first.remediation.plan.coding_prompt == second.remediation.plan.coding_prompt
    assert "# Legal Requirement" in first.remediation.plan.coding_prompt


@pytest.mark.parametrize(
    "reference",
    [_reference(requirement_id=999), _reference(legal_unit_id=999)],
)
def test_llm_cannot_invent_canonical_ids(planner_db, reference):
    finding = _scenario(planner_db)
    client = StaticClient(_document_payload(reference=reference))
    with pytest.raises(RemediationGroundingError):
        plan_remediation(
            planner_db,
            1,
            finding.id,
            _request(RemediationType.DOCUMENT_CHANGE),
            llm_client=client,
        )
    assert planner_db.scalar(select(func.count()).select_from(Remediation)) == 0


def test_invented_file_path_is_rejected(planner_db):
    finding = _scenario(planner_db)
    client = StaticClient(_code_payload("backend/app/routes/delete_account.py"))
    with pytest.raises(RemediationPlanningError, match="file paths absent"):
        plan_remediation(planner_db, 1, finding.id, _request(), llm_client=client)


@pytest.mark.parametrize("target", ["AI chat component", "frontend/src/AiChat.tsx"])
def test_component_or_evidence_backed_path_is_allowed(planner_db, target):
    finding = _scenario(planner_db)
    detail = plan_remediation(
        planner_db, 1, finding.id, _request(), llm_client=StaticClient(_code_payload(target))
    )
    assert target in detail.remediation.plan.affected_files_or_components


def test_document_evidence_metadata_must_match_canonical_context(planner_db):
    finding = _scenario(planner_db)
    client = StaticClient(_document_payload(reference=_reference(regulation_name="Invented Law")))
    with pytest.raises(RemediationGroundingError, match="metadata"):
        plan_remediation(
            planner_db, 1, finding.id, _request(RemediationType.DOCUMENT_CHANGE), llm_client=client
        )


def test_potential_language_preserves_uncertainty(planner_db):
    finding = _scenario(planner_db, gap_status=GapStatus.POTENTIAL)
    detail = plan_remediation(planner_db, 1, finding.id, _request())
    serialized = json.dumps(detail.remediation.plan.model_dump(mode="json")).casefold()
    assert "potential" in serialized or "verify" in serialized
    assert "product violates" not in serialized
    assert "confirmed absent" not in serialized


def test_confirmed_gap_uses_clear_product_gap_language(planner_db):
    finding = _scenario(planner_db, gap_status=GapStatus.CONFIRMED)
    detail = plan_remediation(planner_db, 1, finding.id, _request())
    assert "confirmed gap" in detail.remediation.summary
    assert "confirmed product gap" in json.dumps(
        detail.remediation.plan.model_dump(mode="json")
    ).casefold()


def test_unknown_fact_is_not_converted_to_false_and_document_uses_placeholder(planner_db):
    finding = _scenario(planner_db)
    detail = plan_remediation(
        planner_db, 1, finding.id, _request(RemediationType.DOCUMENT_CHANGE)
    )
    unknown = next(
        item for item in detail.remediation.input_snapshot.relevant_product_facts
        if item.status.value == "UNKNOWN"
    )
    assert unknown.status.value == "UNKNOWN"
    assert "[TO CONFIRM" in detail.remediation.plan.draft_text


def test_not_detected_is_not_confirmed_absence(planner_db):
    finding = _scenario(planner_db)
    detail = plan_remediation(planner_db, 1, finding.id, _request())
    fact = next(item for item in detail.remediation.input_snapshot.relevant_product_facts
                if item.name == "ai_disclosure")
    assert fact.status.value == "NOT_DETECTED"
    assert "confirmed absent" not in json.dumps(
        detail.remediation.plan.model_dump(mode="json")
    ).casefold()


@pytest.mark.parametrize("payload", ["not-json", {}, {"requested_changes": []}])
def test_invalid_llm_output_creates_no_remediation(planner_db, payload):
    finding = _scenario(planner_db)
    with pytest.raises(RemediationPlanningError):
        plan_remediation(
            planner_db, 1, finding.id, _request(), llm_client=StaticClient(payload)
        )
    assert planner_db.scalar(select(func.count()).select_from(Remediation)) == 0


def test_provider_error_creates_no_remediation(planner_db):
    finding = _scenario(planner_db)
    with pytest.raises(RemediationPlanningError, match="provider timeout"):
        plan_remediation(
            planner_db,
            1,
            finding.id,
            _request(),
            llm_client=StaticClient(error=TimeoutError("provider timeout")),
        )
    assert planner_db.scalar(select(func.count()).select_from(Remediation)) == 0


def test_overstated_potential_gap_is_rejected(planner_db):
    finding = _scenario(planner_db)
    payload = _code_payload()
    payload["requested_changes"][0]["change"] = "The product violates the law and is definitely missing the control."
    with pytest.raises(RemediationPlanningError, match="overstates"):
        plan_remediation(
            planner_db, 1, finding.id, _request(), llm_client=StaticClient(payload)
        )


def test_document_without_unknown_placeholder_is_rejected(planner_db):
    finding = _scenario(planner_db)
    client = StaticClient(_document_payload(draft="DRAFT — REQUIRES HUMAN REVIEW."))
    with pytest.raises(RemediationPlanningError, match="placeholder"):
        plan_remediation(
            planner_db, 1, finding.id, _request(RemediationType.DOCUMENT_CHANGE), llm_client=client
        )


def test_persistence_failure_leaves_no_remediation(planner_db, monkeypatch):
    finding = _scenario(planner_db)

    def fail(*args, **kwargs):
        raise RuntimeError("persistence failure")

    monkeypatch.setattr("app.tenant.remediation.planner.create_remediation", fail)
    with pytest.raises(RuntimeError, match="persistence failure"):
        plan_remediation(planner_db, 1, finding.id, _request())
    assert planner_db.scalar(select(func.count()).select_from(Remediation)) == 0


def test_mock_planner_is_deterministic_and_grounded(planner_db):
    finding = _scenario(planner_db)
    request = _request()
    first = plan_remediation(planner_db, 1, finding.id, request)
    second = plan_remediation(planner_db, 1, finding.id, request)
    assert first.remediation.plan.model_dump() == second.remediation.plan.model_dump()
    assert first.remediation.model_provider == "mock"
    assert first.remediation.model_name == "deterministic"


def test_prompt_contract_has_fact_legal_gap_task_sections(planner_db):
    finding = _scenario(planner_db)
    client = StaticClient(_code_payload())
    plan_remediation(planner_db, 1, finding.id, _request(), llm_client=client)
    system, user, _ = client.calls[0]
    assert "Do not invent legal requirements" in system
    parsed = json.loads(user)
    assert {"FACTS", "LEGAL_REQUIREMENTS", "LEGAL_EVIDENCE", "GAP", "TASK"} <= set(parsed)


def test_chain_of_thought_field_is_rejected_and_not_saved(planner_db):
    finding = _scenario(planner_db)
    client = StaticClient(_code_payload(chain_of_thought="hidden reasoning"))
    with pytest.raises(RemediationPlanningError, match="schema validation"):
        plan_remediation(planner_db, 1, finding.id, _request(), llm_client=client)
    assert planner_db.scalar(select(func.count()).select_from(Remediation)) == 0


def test_planner_does_not_mutate_finding_or_agent_run(planner_db):
    finding = _scenario(planner_db)
    run = planner_db.get(TenantAgentRun, finding.run_id)
    before_output = json.loads(json.dumps(run.output_json))
    plan_remediation(planner_db, 1, finding.id, _request())
    planner_db.refresh(finding)
    planner_db.refresh(run)
    assert finding.status == "OPEN"
    assert run.output_json == before_output
