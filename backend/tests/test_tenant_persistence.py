"""Tenant Agent run, finding, evidence and missing-context persistence."""

import json

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models import (
    Company,
    Finding,
    FindingEvidence,
    FindingRequirement,
    LegalUnit,
    Product,
    ProductTwinVersion,
    Regulation,
    RegulationVersion,
    Requirement,
    TenantAgentRun,
    TenantMissingContextItem,
)
from app.tenant.applicability.schemas import ApplicabilityResult, DecisionSource, MissingContextItem
from app.tenant.context.ownership import TenantProductMismatchError
from app.tenant.context.schemas import ProductContext, ProductFactContext
from app.tenant.findings import (
    FindingCandidate,
    FindingPersistenceError,
    ImpactLevel,
    TenantAgentRunStatus,
    TenantTriggerType,
    build_input_snapshot,
    create_agent_run,
    load_finding,
    mark_run_failed,
    mark_run_needs_user_input,
    persist_findings,
)
from app.tenant.gap.schemas import GapAnalysisResult, GapStatus, GapType
from app.tenant.regulatory.schemas import (
    LegalEvidence,
    RegulationSourceContext,
    RegulationTrigger,
    RequirementContext,
)


@pytest.fixture
def persistence(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'tenant-persistence.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([Company(id=1, name="Tenant A"), Company(id=2, name="Tenant B")])
        db.flush()
        db.add_all([
            Product(id=1, company_id=1, name="Product A"),
            Product(id=2, company_id=2, name="Product B"),
        ])
        db.flush()
        regulation = Regulation(id=1, name="EU Test Act", jurisdiction="EU",
                                canonical_source_url="https://example.eu/act")
        db.add(regulation)
        db.flush()
        version = RegulationVersion(id=1, regulation_id=1, version_number=1,
                                    normalized_text="Article 1", content_hash="a" * 64,
                                    is_current=True)
        db.add(version)
        db.flush()
        regulation.current_version_id = version.id
        db.add(LegalUnit(id=1, version_id=1, unit_type="article", unit_number="Article 1",
                         heading="Transparency", text="Providers shall publish information."))
        db.flush()
        db.add(Requirement(
            id=1, regulation_id=1, version_id=1, legal_unit_id=1,
            requirement_type="obligation", subject_type="provider", action_type="inform",
            object_type="AI system", conditions_json=[], exceptions_json=[],
            summary="Publish transparency information", confidence=.9, status="ACTIVE",
        ))
        twin = ProductTwinVersion(id=1, product_id=1, version_number=1, reason="test")
        db.add(twin)
        db.commit()
        yield db


def _contexts(*, twin_id=1, secret=False):
    evidence_dict = {"reason": "observed"}
    payload = {"topics": ["透明度"]}
    if secret:
        evidence_dict.update({"secret": "do-not-store", "token": "do-not-store"})
        payload["authorization"] = "Bearer do-not-store"
    product = ProductContext(
        tenant_id=1,
        product_id=1,
        product_twin_version_id=twin_id,
        product_twin_version_number=1 if twin_id else None,
        facts=[ProductFactContext(
            fact_id=1 if twin_id else None,
            group="controls",
            name="ai_disclosure",
            status="PRESENT",
            value="ai_disclosure",
            source="USER",
            confidence=1,
            evidence=[evidence_dict],
            scan_scope={},
            review_status="CONFIRMED",
            is_user_confirmed=True,
        )],
        used_legacy_fallback=twin_id is None,
    )
    trigger = RegulationTrigger(
        event_id="evt_1",
        event_type="regulation.change.ready",
        regulation_id=1,
        version_id=1,
        change_ids=[1],
        materiality="HIGH",
        topics=["透明度"],
        requirement_ids=[1],
        legal_unit_ids=[1],
        payload=payload,
        source=RegulationSourceContext(
            regulation_name="EU Test Act", jurisdiction="EU", version=1,
            source_url="https://example.eu/act",
        ),
    )
    requirement = RequirementContext(
        id=1, regulation_id=1, version_id=1, legal_unit_id=1,
        requirement_type="obligation", subject_type="provider", action_type="inform",
        object_type="AI system", conditions=[], exceptions=[],
        summary="Publish transparency information", confidence=.9, status="ACTIVE",
        regulation_name="EU Test Act", jurisdiction="EU", regulation_version=1,
        source_url="https://example.eu/act",
    )
    evidence = LegalEvidence(
        legal_unit_id=1, regulation_id=1, regulation_name="EU Test Act",
        version_id=1, version=1, article="Article 1", heading="Transparency",
        content="Providers shall publish information.", source_url="https://example.eu/act",
        requirement_ids=[1],
    )
    return product, trigger, requirement, evidence


def _run(db, *, product_id=1, twin_id=1, secret=False):
    product, trigger, requirement, evidence = _contexts(twin_id=twin_id, secret=secret)
    if product_id != 1:
        product = product.model_copy(update={"product_id": product_id})
    snapshot = build_input_snapshot(product, trigger, [requirement], [evidence])
    return create_agent_run(
        db,
        tenant_id=1,
        product_id=product_id,
        trigger_type=TenantTriggerType.REGULATION_CHANGE,
        trigger_id=trigger.event_id,
        input_snapshot=snapshot,
        model_provider="mock",
        model_name="deterministic",
        prompt_version="tenant-v1",
    )


def _candidate(status=GapStatus.POTENTIAL, *, applies=True, twin_id=1, evidence=None):
    _, _, requirement, default_evidence = _contexts(twin_id=twin_id)
    applicability = ApplicabilityResult(
        requirement_id=1,
        applies=applies,
        confidence=.9 if applies is not None else 0,
        reasoning_summary="The product is in scope." if applies else "The product is not in scope.",
        decision_source=DecisionSource.DETERMINISTIC if applies is not None else DecisionSource.INSUFFICIENT_CONTEXT,
    )
    gap = GapAnalysisResult(
        requirement_id=1,
        gap_status=status,
        gap_type=(GapType.MISSING_CONTROL if status == GapStatus.CONFIRMED
                  else GapType.INSUFFICIENT_EVIDENCE if status == GapStatus.POTENTIAL
                  else GapType.UNKNOWN),
        current_state="Current control state",
        required_state="Publish transparency information",
        confidence=.8,
        reasoning_summary=f"Gap status is {status.value}.",
    )
    return FindingCandidate(
        title="AI transparency control gap",
        impact_level=ImpactLevel.HIGH,
        confidence=.8,
        applicability=applicability,
        gap=gap,
        requirements=[requirement],
        legal_evidence=[default_evidence if evidence is None else evidence],
        product_twin_version_id=twin_id,
    )


def test_create_run_and_snapshot_is_sanitized_and_immutable(persistence):
    run = _run(persistence, secret=True)

    assert run.status == "PENDING"
    assert run.tenant_id == 1 and run.product_id == 1
    serialized = json.dumps(run.input_snapshot_json)
    assert "do-not-store" not in serialized
    before = run.input_snapshot_json
    mark_run_failed(persistence, run.id, "test failure")
    assert persistence.get(TenantAgentRun, run.id).input_snapshot_json == before


def test_ownership_mismatch_is_rejected(persistence):
    with pytest.raises(TenantProductMismatchError):
        _run(persistence, product_id=2)


def test_needs_user_input_persists_question_without_finding(persistence):
    run = _run(persistence)
    item = MissingContextItem(
        requirement_id=1,
        field_path="data_types.biometric",
        question="Does the product process biometric data?",
        reason="Applicability depends on this fact.",
    )
    undecided = ApplicabilityResult(
        requirement_id=1,
        applies=None,
        confidence=0,
        missing_context=[item],
        reasoning_summary="Product context is incomplete.",
        decision_source=DecisionSource.INSUFFICIENT_CONTEXT,
    )

    updated = mark_run_needs_user_input(
        persistence, run.id, [item], applicability_results=[undecided]
    )

    assert updated.status == "NEEDS_USER_INPUT"
    assert updated.output_json["applicability_results"][0]["applies"] is None
    assert persistence.scalar(select(func.count()).select_from(TenantMissingContextItem)) == 1
    assert persistence.scalar(select(func.count()).select_from(Finding)) == 0


def test_undecided_candidate_derives_missing_context_without_finding(persistence):
    run = _run(persistence)
    item = MissingContextItem(
        requirement_id=1,
        field_path="target_users",
        question="Who are the target users?",
        reason="Applicability depends on the target users.",
    )
    candidate = _candidate()
    candidate = candidate.model_copy(update={
        "applicability": ApplicabilityResult(
            requirement_id=1,
            applies=None,
            confidence=0,
            missing_context=[item],
            reasoning_summary="Target users are unknown.",
            decision_source=DecisionSource.INSUFFICIENT_CONTEXT,
        ),
        "gap": None,
    })

    findings = persist_findings(persistence, run.id, [candidate])

    assert findings == []
    assert persistence.get(TenantAgentRun, run.id).status == "NEEDS_USER_INPUT"
    assert persistence.scalar(select(func.count()).select_from(TenantMissingContextItem)) == 1


@pytest.mark.parametrize("status", [GapStatus.POTENTIAL, GapStatus.CONFIRMED])
def test_eligible_gap_persists_finding_and_canonical_trace(persistence, status):
    run = _run(persistence)

    findings = persist_findings(persistence, run.id, [_candidate(status)])
    detail = load_finding(persistence, 1, findings[0].id)

    assert len(findings) == 1
    assert findings[0].product_twin_version_id == 1
    assert persistence.get(FindingRequirement, (findings[0].id, 1)) is not None
    evidence = persistence.scalar(select(FindingEvidence).where(FindingEvidence.finding_id == findings[0].id))
    assert evidence.legal_unit_id == 1 and evidence.requirement_id == 1
    assert evidence.evidence_snapshot_json["article"] == "Article 1"
    assert detail is not None
    assert detail.requirements[0].id == 1
    assert detail.legal_evidence[0].source_url == "https://example.eu/act"
    assert detail.evidence_snapshots[0].snapshot.content.startswith("Providers")


@pytest.mark.parametrize(
    "gap_status,applies",
    [(GapStatus.NO_GAP, True), (GapStatus.UNKNOWN, True), (GapStatus.POTENTIAL, False)],
)
def test_ineligible_analysis_does_not_create_finding(persistence, gap_status, applies):
    run = _run(persistence)

    findings = persist_findings(persistence, run.id, [_candidate(gap_status, applies=applies)])

    assert findings == []
    assert persistence.get(TenantAgentRun, run.id).status == "COMPLETED"


def test_legacy_fallback_finding_allows_null_twin_version(persistence):
    run = _run(persistence, twin_id=None)

    finding = persist_findings(persistence, run.id, [_candidate(twin_id=None)])[0]

    assert finding.product_twin_version_id is None
    assert persistence.get(TenantAgentRun, run.id).input_snapshot_json["product_context"]["used_legacy_fallback"] is True


def test_duplicate_finding_requirement_is_rejected_by_database(persistence):
    run = _run(persistence)
    finding = persist_findings(persistence, run.id, [_candidate()])[0]
    persistence.add(FindingRequirement(finding_id=finding.id, requirement_id=1))

    with pytest.raises(IntegrityError):
        persistence.commit()
    persistence.rollback()


def test_transaction_failure_rolls_back_finding_and_marks_run_failed(persistence):
    run = _run(persistence)
    bad_evidence = _contexts()[3].model_copy(update={"legal_unit_id": 999})

    with pytest.raises(FindingPersistenceError):
        persist_findings(persistence, run.id, [_candidate(evidence=bad_evidence)])

    assert persistence.scalar(select(func.count()).select_from(Finding)) == 0
    failed = persistence.get(TenantAgentRun, run.id)
    assert failed.status == "FAILED"
    assert "unknown legal unit 999" in failed.error


def test_mark_failed_records_error(persistence):
    run = _run(persistence)

    failed = mark_run_failed(persistence, run.id, "provider unavailable")

    assert failed.status == TenantAgentRunStatus.FAILED.value
    assert failed.error == "provider unavailable"
