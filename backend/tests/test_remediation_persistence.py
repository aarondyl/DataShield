"""Persistence, traceability, immutable snapshots, and decisions for Remediation."""

import json

import pytest
from sqlalchemy import create_engine, func, select
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
    Remediation,
    RemediationEvidence,
    RemediationRequirement,
    Requirement,
    TenantAgentRun,
)
from app.tenant.applicability.schemas import ApplicabilityResult, DecisionSource
from app.tenant.context.schemas import ProductFactContext
from app.tenant.gap.schemas import GapAnalysisResult, GapStatus, GapType
from app.tenant.regulatory.schemas import LegalEvidence, RequirementContext
from app.tenant.remediation import (
    CodeChangeProposal,
    CodeTestInstruction,
    DocumentChangePlan,
    ProposedDocumentChange,
    RemediationConflictError,
    RemediationCreateRequest,
    RemediationGroundingError,
    RemediationNotFoundError,
    RemediationPersistenceError,
    RemediationPlanningInput,
    RemediationStatus,
    RemediationType,
    RequestedCodeChange,
    approve_remediation,
    build_code_change_plan,
    create_remediation,
    get_remediation,
    list_remediations_for_finding,
    load_authoritative_gap_context,
    reject_remediation,
)
from app.understanding.schemas import FindingStatus


@pytest.fixture
def persistence(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'remediation.db'}")
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
            name="Example Regulation",
            jurisdiction="EU",
            canonical_source_url="https://regulator.example/law",
        )
        db.add(regulation)
        db.flush()
        version = RegulationVersion(
            id=1,
            regulation_id=1,
            version_number=1,
            normalized_text="Articles 1 and 2",
            content_hash="a" * 64,
            is_current=True,
        )
        db.add(version)
        db.flush()
        regulation.current_version_id = version.id
        db.add_all([
            LegalUnit(
                id=1,
                version_id=1,
                unit_type="article",
                unit_number="Article 1",
                heading="Transparency",
                text="Providers shall publish transparency information.",
            ),
            LegalUnit(
                id=2,
                version_id=1,
                unit_type="article",
                unit_number="Article 2",
                heading="Other duty",
                text="A separate duty.",
            ),
        ])
        db.flush()
        db.add_all([
            Requirement(
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
                summary="Publish transparency information",
                confidence=.9,
                status="ACTIVE",
            ),
            Requirement(
                id=2,
                regulation_id=1,
                version_id=1,
                legal_unit_id=2,
                requirement_type="obligation",
                subject_type="provider",
                action_type="document",
                object_type="other duty",
                conditions_json=[],
                exceptions_json=[],
                summary="Document another control",
                confidence=.8,
                status="ACTIVE",
            ),
        ])
        db.add(ProductTwinVersion(id=1, product_id=1, version_number=1, reason="test"))
        db.commit()
        yield db


def _requirement(requirement_id=1, legal_unit_id=1):
    summary = "Publish transparency information" if requirement_id == 1 else "Document another control"
    return RequirementContext(
        id=requirement_id,
        regulation_id=1,
        version_id=1,
        legal_unit_id=legal_unit_id,
        requirement_type="obligation",
        subject_type="provider",
        action_type="inform",
        object_type="AI system",
        conditions=[],
        exceptions=[],
        summary=summary,
        confidence=.9,
        status="ACTIVE",
        regulation_name="Example Regulation",
        jurisdiction="EU",
        regulation_version=1,
        source_url="https://regulator.example/law",
    )


def _evidence(requirement_id=1, legal_unit_id=1):
    return LegalEvidence(
        legal_unit_id=legal_unit_id,
        regulation_id=1,
        regulation_name="Example Regulation",
        version_id=1,
        version=1,
        article=f"Article {legal_unit_id}",
        heading="Transparency" if legal_unit_id == 1 else "Other duty",
        content=(
            "Providers shall publish transparency information."
            if legal_unit_id == 1 else "A separate duty."
        ),
        source_url="https://regulator.example/law",
        requirement_ids=[requirement_id],
    )


def _fact(*, secret=False):
    evidence = {"file": "components/account", "reason": "selected evidence"}
    if secret:
        evidence.update({"authorization": "Bearer hidden", "token": "hidden"})
    return ProductFactContext(
        fact_id=10,
        group="controls",
        name="ai_disclosure",
        status=FindingStatus.NOT_DETECTED,
        source="REPOSITORY",
        confidence=.8,
        evidence=[evidence],
        scan_scope={"analysis_mode": "SELECTED_PATHS"},
        review_status="UNREVIEWED",
    )


def _analysis_results(requirement_id=1):
    applicability = ApplicabilityResult(
        requirement_id=requirement_id,
        applies=True,
        confidence=.9,
        reasoning_summary="The product and requirement are in scope.",
        decision_source=DecisionSource.DETERMINISTIC,
    )
    gap = GapAnalysisResult(
        requirement_id=requirement_id,
        gap_status=GapStatus.POTENTIAL,
        gap_type=GapType.INSUFFICIENT_EVIDENCE,
        current_state="No disclosure control was detected in the selected scan scope.",
        required_state="Publish transparency information.",
        affected_assets=["AI interaction component"],
        confidence=.8,
        reasoning_summary="The selected scan did not detect the required disclosure control.",
        supporting_fact_ids=[10],
    )
    return applicability, gap


def _finding(db, *, tenant_id=1, product_id=1, status="OPEN", twin_id=1, secret=False):
    applicability, gap = _analysis_results()
    fact = _fact(secret=secret)
    run = TenantAgentRun(
        tenant_id=tenant_id,
        product_id=product_id,
        trigger_type="MANUAL_SCAN",
        trigger_id=None,
        status="COMPLETED",
        model_provider="mock",
        model_name="deterministic",
        prompt_version="tenant-applicability-v1",
        input_snapshot_json={
            "tenant_id": tenant_id,
            "product_id": product_id,
            "product_twin_version_id": twin_id,
            "product_context": {"facts": [fact.model_dump(mode="json")]},
        },
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
        tenant_id=tenant_id,
        product_id=product_id,
        trigger_type="MANUAL_SCAN",
        title="AI transparency disclosure may be missing",
        status=status,
        impact_level="HIGH",
        confidence=.8,
        applicability_summary=applicability.reasoning_summary,
        gap_status=gap.gap_status.value,
        gap_type=gap.gap_type.value,
        gap_summary=gap.reasoning_summary,
        product_twin_version_id=twin_id,
    )
    db.add(finding)
    db.flush()
    run.output_json = {**run.output_json, "finding_ids": [finding.id]}
    db.add(FindingRequirement(finding_id=finding.id, requirement_id=1))
    db.add(FindingEvidence(
        finding_id=finding.id,
        legal_unit_id=1,
        requirement_id=1,
        evidence_snapshot_json=_evidence().model_dump(mode="json"),
    ))
    db.commit()
    db.refresh(finding)
    return finding


def _planning_input(finding, *, remediation_type=RemediationType.CODE_CHANGE, secret=False,
                    requirement=None, evidence=None):
    applicability, gap = _analysis_results()
    requirement = requirement or _requirement()
    evidence = evidence or _evidence()
    return RemediationPlanningInput(
        finding_id=finding.id,
        tenant_id=finding.tenant_id,
        product_id=finding.product_id,
        finding_title=finding.title,
        impact_level=finding.impact_level,
        finding_confidence=finding.confidence,
        applicability_summary=finding.applicability_summary,
        gap_status=finding.gap_status,
        gap_type=finding.gap_type,
        gap_summary=finding.gap_summary,
        gap_current_state=gap.current_state,
        gap_required_state=gap.required_state,
        product_twin_version_id=finding.product_twin_version_id,
        requirements=[requirement],
        legal_evidence=[evidence],
        relevant_product_facts=[_fact(secret=secret)],
        planner_request=RemediationCreateRequest(
            tenant_id=finding.tenant_id,
            remediation_type=remediation_type,
            document_type=(
                "PRIVACY_POLICY"
                if remediation_type == RemediationType.DOCUMENT_CHANGE else None
            ),
        ),
    )


def _code_plan(planning_input):
    proposal = CodeChangeProposal(
        requested_changes=[RequestedCodeChange(
            target="AI interaction component",
            change="Add a visible disclosure.",
            rationale="Address the persisted transparency Finding.",
        )],
        affected_files_or_components=["AI interaction component"],
        constraints=["Preserve unrelated behavior"],
        acceptance_criteria=["The disclosure is visible before interaction."],
        tests=[CodeTestInstruction(
            name="disclosure visibility",
            purpose="Verify the disclosure appears.",
            expected_result="The disclosure is visible before AI interaction.",
        )],
        do_not_modify=["unrelated authentication"],
    )
    return build_code_change_plan(planning_input, proposal)


def _document_plan(planning_input, *, evidence_reference=None):
    evidence = planning_input.legal_evidence[0]
    reference = evidence_reference or {
        "requirement_id": 1,
        "legal_unit_id": 1,
        "regulation_id": evidence.regulation_id,
        "regulation_name": evidence.regulation_name,
        "version_id": evidence.version_id,
        "version": evidence.version,
        "article": evidence.article,
        "heading": evidence.heading,
        "source_url": evidence.source_url,
    }
    return DocumentChangePlan(
        document_type="PRIVACY_POLICY",
        issue=planning_input.finding_title,
        current_state=planning_input.gap_current_state,
        required_state=planning_input.gap_required_state,
        proposed_changes=[ProposedDocumentChange(
            section="AI transparency",
            change="Add a draft disclosure.",
            rationale="Address the persisted Finding.",
        )],
        draft_text="Draft disclosure requiring human review.",
        evidence=[reference],
        acceptance_criteria=["A human reviewer confirms product accuracy."],
    )


def _create(db, finding, *, remediation_type=RemediationType.CODE_CHANGE, secret=False):
    context = _planning_input(finding, remediation_type=remediation_type, secret=secret)
    plan = _code_plan(context) if remediation_type == RemediationType.CODE_CHANGE else _document_plan(context)
    return create_remediation(
        db,
        planning_input=context,
        plan=plan,
        title="Address AI transparency",
        summary="A grounded remediation proposal.",
        model_provider="mock",
        model_name="deterministic",
        prompt_version="remediation-v1",
    )


@pytest.mark.parametrize("remediation_type", [RemediationType.CODE_CHANGE, RemediationType.DOCUMENT_CHANGE])
def test_create_remediation_types_and_trace(persistence, remediation_type):
    finding = _finding(persistence)
    record = _create(persistence, finding, remediation_type=remediation_type)
    assert record.remediation_type == remediation_type
    assert record.status == RemediationStatus.PROPOSED
    assert persistence.get(RemediationRequirement, (record.id, 1)) is not None
    evidence = persistence.scalar(select(RemediationEvidence).where(
        RemediationEvidence.remediation_id == record.id
    ))
    assert evidence.legal_unit_id == 1 and evidence.requirement_id == 1


def test_missing_finding_and_cross_tenant_are_not_found(persistence):
    finding = _finding(persistence)
    context = _planning_input(finding)
    plan = _code_plan(context)
    for finding_id, tenant_id in ((999, 1), (finding.id, 2)):
        bad = context.model_copy(update={
            "finding_id": finding_id,
            "tenant_id": tenant_id,
            "planner_request": context.planner_request.model_copy(update={"tenant_id": tenant_id}),
        })
        with pytest.raises(RemediationNotFoundError):
            create_remediation(
                persistence, planning_input=bad, plan=plan, title="title", summary="summary"
            )


@pytest.mark.parametrize("status", ["DISMISSED", "RESOLVED"])
def test_non_open_finding_rejects_creation(persistence, status):
    finding = _finding(persistence, status=status)
    context = _planning_input(finding)
    with pytest.raises(RemediationConflictError, match=status):
        create_remediation(
            persistence,
            planning_input=context,
            plan=_code_plan(context),
            title="title",
            summary="summary",
        )


def test_one_finding_allows_multiple_remediations(persistence):
    finding = _finding(persistence)
    first = _create(persistence, finding)
    second = _create(persistence, finding)
    assert first.id != second.id
    assert len(list_remediations_for_finding(persistence, 1, finding.id)) == 2


def test_requirement_and_legal_unit_must_be_finding_subsets(persistence):
    finding = _finding(persistence)
    foreign_requirement = _requirement(2, 2)
    foreign_evidence = _evidence(2, 2)
    bad_requirement = _planning_input(
        finding, requirement=foreign_requirement, evidence=foreign_evidence
    )
    with pytest.raises(RemediationGroundingError, match="requirements outside"):
        create_remediation(
            persistence,
            planning_input=bad_requirement,
            plan=_code_plan(bad_requirement),
            title="title",
            summary="summary",
        )

    bad_unit = _planning_input(finding, evidence=_evidence(1, 2))
    with pytest.raises(RemediationGroundingError, match="legal units outside"):
        create_remediation(
            persistence,
            planning_input=bad_unit,
            plan=_code_plan(bad_unit),
            title="title",
            summary="summary",
        )


def test_product_twin_reference_and_legacy_null_are_preserved(persistence):
    finding = _finding(persistence)
    assert _create(persistence, finding).product_twin_version_id == 1

    legacy = _finding(persistence, twin_id=None)
    record = _create(persistence, legacy)
    assert record.product_twin_version_id is None
    assert record.input_snapshot.product_twin_version_id is None


def test_plan_and_input_snapshot_are_not_changed_by_decisions(persistence):
    finding = _finding(persistence)
    record = _create(persistence, finding)
    before_plan = record.plan.model_dump(mode="json")
    before_input = record.input_snapshot.model_dump(mode="json")
    approve_remediation(persistence, 1, record.id, note="reviewed")
    after = get_remediation(persistence, 1, record.id).remediation
    assert after.plan.model_dump(mode="json") == before_plan
    assert after.input_snapshot.model_dump(mode="json") == before_input


def test_input_snapshot_is_minimal_and_sanitized(persistence):
    finding = _finding(persistence, secret=True)
    record = _create(persistence, finding, secret=True)
    raw = persistence.get(Remediation, record.id).input_snapshot_json
    assert set(raw) == {
        "finding", "applicability_result", "gap_result", "requirements",
        "legal_evidence", "relevant_product_facts", "planner_request",
        "product_twin_version_id",
    }
    serialized = json.dumps(raw)
    assert "Bearer hidden" not in serialized
    assert '"token"' not in serialized
    assert "product_context" not in raw


def test_authoritative_gap_is_aligned_by_requirement_id(persistence):
    finding = _finding(persistence)
    _, other_gap = _analysis_results(requirement_id=2)
    run = persistence.get(TenantAgentRun, finding.run_id)
    run.output_json = {
        **run.output_json,
        "gap_results": [other_gap.model_dump(mode="json"), *run.output_json["gap_results"]],
    }
    persistence.commit()
    gap = load_authoritative_gap_context(persistence, finding, requirement_id=1)
    assert gap.requirement_id == 1


def test_missing_authoritative_gap_fails_closed(persistence):
    finding = _finding(persistence)
    run = persistence.get(TenantAgentRun, finding.run_id)
    run.output_json = {**run.output_json, "gap_results": []}
    persistence.commit()
    with pytest.raises(RemediationPersistenceError, match="no authoritative Gap"):
        _create(persistence, finding)


@pytest.mark.parametrize(
    ("decision", "expected"),
    [(approve_remediation, RemediationStatus.APPROVED), (reject_remediation, RemediationStatus.REJECTED)],
)
def test_decisions_are_idempotent_and_do_not_change_finding(persistence, decision, expected):
    finding = _finding(persistence)
    record = _create(persistence, finding)
    first = decision(persistence, 1, record.id, note="reviewed")
    second = decision(persistence, 1, record.id, note="ignored on idempotent call")
    assert first.status == second.status == expected
    assert persistence.get(Finding, finding.id).status == "OPEN"


@pytest.mark.parametrize(
    ("first,second"),
    [(approve_remediation, reject_remediation), (reject_remediation, approve_remediation)],
)
def test_opposite_terminal_transition_conflicts(persistence, first, second):
    finding = _finding(persistence)
    record = _create(persistence, finding)
    first(persistence, 1, record.id)
    with pytest.raises(RemediationConflictError):
        second(persistence, 1, record.id)


def test_failed_creation_leaves_no_partial_remediation(persistence, monkeypatch):
    finding = _finding(persistence)
    context = _planning_input(finding)
    original_add_all = persistence.add_all

    def fail_on_requirement_links(instances):
        rows = list(instances)
        if rows and isinstance(rows[0], RemediationRequirement):
            raise RuntimeError("simulated association insert failure")
        return original_add_all(rows)

    monkeypatch.setattr(persistence, "add_all", fail_on_requirement_links)
    with pytest.raises(RuntimeError, match="simulated association"):
        create_remediation(
            persistence,
            planning_input=context,
            plan=_code_plan(context),
            title="title",
            summary="summary",
        )
    assert persistence.scalar(select(func.count()).select_from(Remediation)) == 0
    assert persistence.scalar(select(func.count()).select_from(RemediationRequirement)) == 0
    assert persistence.scalar(select(func.count()).select_from(RemediationEvidence)) == 0


def test_detail_reloads_canonical_requirement_legal_unit_and_twin(persistence):
    finding = _finding(persistence)
    record = _create(persistence, finding)
    detail = get_remediation(persistence, 1, record.id)
    assert detail.finding.id == finding.id
    assert detail.requirements[0].id == 1
    assert detail.legal_evidence[0].legal_unit_id == 1
    assert detail.evidence_references[0].requirement_id == 1
    assert detail.product_twin_version.id == 1


def test_service_exposes_no_plan_update_operation():
    from app.tenant.remediation import service

    assert not hasattr(service, "update_remediation")
    assert not hasattr(service, "update_plan")
