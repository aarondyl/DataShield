"""Transactional persistence and canonical queries for remediation plans."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Finding,
    FindingEvidence,
    FindingRequirement,
    ProductTwinVersion,
    Remediation,
    RemediationEvidence,
    RemediationRequirement,
    TenantAgentRun,
)
from app.tenant.applicability.schemas import ApplicabilityResult
from app.tenant.context.ownership import (
    ProductNotFoundError,
    TenantNotFoundError,
    TenantProductMismatchError,
    resolve_tenant,
    resolve_tenant_product,
)
from app.tenant.context.schemas import ProductFactContext
from app.tenant.findings.schemas import FindingRecord
from app.tenant.findings.service import load_finding
from app.tenant.gap.schemas import GapAnalysisResult
from app.tenant.regulatory.service import load_legal_evidence, load_requirement_contexts
from app.tenant.remediation.schemas import (
    CodeChangePlan,
    DocumentChangePlan,
    RemediationDetail,
    RemediationEvidenceReference,
    RemediationGroundingError,
    RemediationInputSnapshot,
    RemediationListItem,
    RemediationPlanningInput,
    RemediationProductTwinVersionReference,
    RemediationRecord,
    RemediationStatus,
    RemediationType,
    validate_remediation_grounding,
)


class RemediationPersistenceError(RuntimeError):
    pass


class RemediationNotFoundError(RemediationPersistenceError):
    pass


class RemediationConflictError(RemediationPersistenceError):
    pass


_FORBIDDEN_SNAPSHOT_KEYS = {
    "api_key",
    "llm_key",
    "authorization",
    "password",
    "secret",
    "token",
    "access_token",
    "refresh_token",
    "bearer",
}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _sanitize(value):
    if isinstance(value, dict):
        clean = {}
        for key, item in value.items():
            normalized = str(key).casefold()
            if normalized in _FORBIDDEN_SNAPSHOT_KEYS or normalized.endswith("_token"):
                continue
            clean[key] = _sanitize(item)
        return clean
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    return value


def _finding_record(row: Finding) -> FindingRecord:
    return FindingRecord(
        id=row.id,
        run_id=row.run_id,
        tenant_id=row.tenant_id,
        product_id=row.product_id,
        trigger_type=row.trigger_type,
        trigger_id=row.trigger_id,
        title=row.title,
        status=row.status,
        impact_level=row.impact_level,
        confidence=row.confidence,
        applicability_summary=row.applicability_summary,
        gap_status=row.gap_status,
        gap_type=row.gap_type,
        gap_summary=row.gap_summary,
        product_twin_version_id=row.product_twin_version_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _owned_finding(db: Session, tenant_id: int, finding_id: int) -> Finding:
    try:
        resolve_tenant(db, tenant_id)
    except TenantNotFoundError as exc:
        raise RemediationNotFoundError("Finding does not exist for this tenant") from exc
    finding = db.scalar(
        select(Finding).where(Finding.id == finding_id, Finding.tenant_id == tenant_id)
    )
    if finding is None:
        raise RemediationNotFoundError("Finding does not exist for this tenant")
    try:
        resolve_tenant_product(db, tenant_id, finding.product_id)
    except (ProductNotFoundError, TenantProductMismatchError) as exc:
        raise RemediationNotFoundError("Finding does not exist for this tenant") from exc
    return finding


def _owned_remediation(db: Session, tenant_id: int, remediation_id: int) -> Remediation:
    try:
        resolve_tenant(db, tenant_id)
    except TenantNotFoundError as exc:
        raise RemediationNotFoundError("Remediation does not exist for this tenant") from exc
    row = db.scalar(
        select(Remediation).where(
            Remediation.id == remediation_id,
            Remediation.tenant_id == tenant_id,
        )
    )
    if row is None:
        raise RemediationNotFoundError("Remediation does not exist for this tenant")
    try:
        resolve_tenant_product(db, tenant_id, row.product_id)
    except (ProductNotFoundError, TenantProductMismatchError) as exc:
        raise RemediationNotFoundError("Remediation does not exist for this tenant") from exc
    return row


def _run_for_finding(db: Session, finding: Finding) -> TenantAgentRun:
    run = db.get(TenantAgentRun, finding.run_id)
    if run is None or run.tenant_id != finding.tenant_id or run.product_id != finding.product_id:
        raise RemediationPersistenceError("Finding has no valid canonical Tenant Agent run")
    return run


def _linked_requirement_ids(db: Session, finding_id: int) -> list[int]:
    return list(
        db.scalars(
            select(FindingRequirement.requirement_id)
            .where(FindingRequirement.finding_id == finding_id)
            .order_by(FindingRequirement.requirement_id)
        ).all()
    )


def load_authoritative_gap_context(
    db: Session,
    finding: Finding,
    *,
    requirement_id: int | None = None,
) -> GapAnalysisResult:
    """Load the exact persisted Gap result for a Finding-linked Requirement."""

    run = _run_for_finding(db, finding)
    linked_ids = set(_linked_requirement_ids(db, finding.id))
    if requirement_id is not None and requirement_id not in linked_ids:
        raise RemediationPersistenceError(
            f"Requirement {requirement_id} is not linked to Finding {finding.id}"
        )
    results: list[GapAnalysisResult] = []
    try:
        for payload in (run.output_json or {}).get("gap_results", []):
            result = GapAnalysisResult.model_validate(payload)
            if result.requirement_id not in linked_ids:
                continue
            if requirement_id is not None and result.requirement_id != requirement_id:
                continue
            if (
                result.gap_status.value == finding.gap_status
                and result.gap_type.value == finding.gap_type
                and result.reasoning_summary == finding.gap_summary
            ):
                results.append(result)
    except (TypeError, ValidationError) as exc:
        raise RemediationPersistenceError("Tenant Agent gap output is invalid") from exc
    if not results:
        raise RemediationPersistenceError(
            "Finding has no authoritative Gap result aligned by requirement_id"
        )
    if len(results) != 1:
        raise RemediationPersistenceError(
            "Finding has multiple authoritative Gap results; requirement alignment is ambiguous"
        )
    return results[0]


def _load_authoritative_applicability(
    db: Session, finding: Finding, requirement_id: int
) -> ApplicabilityResult:
    run = _run_for_finding(db, finding)
    matches: list[ApplicabilityResult] = []
    try:
        for payload in (run.output_json or {}).get("applicability_results", []):
            result = ApplicabilityResult.model_validate(payload)
            if (
                result.requirement_id == requirement_id
                and result.reasoning_summary == finding.applicability_summary
            ):
                matches.append(result)
    except (TypeError, ValidationError) as exc:
        raise RemediationPersistenceError("Tenant Agent applicability output is invalid") from exc
    if len(matches) != 1:
        raise RemediationPersistenceError(
            "Finding has no unique authoritative Applicability result aligned by requirement_id"
        )
    return matches[0]


def _validate_planning_input(
    db: Session,
    finding: Finding,
    planning_input: RemediationPlanningInput,
    gap: GapAnalysisResult,
) -> None:
    expected = {
        "finding_id": finding.id,
        "tenant_id": finding.tenant_id,
        "product_id": finding.product_id,
        "finding_title": finding.title,
        "impact_level": finding.impact_level,
        "finding_confidence": finding.confidence,
        "applicability_summary": finding.applicability_summary,
        "gap_status": finding.gap_status,
        "gap_type": finding.gap_type,
        "gap_summary": finding.gap_summary,
        "product_twin_version_id": finding.product_twin_version_id,
    }
    actual = planning_input.model_dump()
    for field, value in expected.items():
        if actual[field] != value:
            raise RemediationPersistenceError(
                f"Planning input {field} does not match Finding {finding.id}"
            )
    if planning_input.gap_current_state != gap.current_state:
        raise RemediationPersistenceError("Planning input current_state is not authoritative")
    if planning_input.gap_required_state != gap.required_state:
        raise RemediationPersistenceError("Planning input required_state is not authoritative")

    run = _run_for_finding(db, finding)
    raw_facts = ((run.input_snapshot_json or {}).get("product_context") or {}).get("facts", [])
    trusted_facts = [ProductFactContext.model_validate(item).model_dump(mode="json") for item in raw_facts]
    for fact in planning_input.relevant_product_facts:
        if fact.model_dump(mode="json") not in trusted_facts:
            raise RemediationPersistenceError(
                f"Product fact {fact.fact_id or fact.name} is not in the Finding input snapshot"
            )


def _build_input_snapshot(
    finding: Finding,
    planning_input: RemediationPlanningInput,
    applicability: ApplicabilityResult,
    gap: GapAnalysisResult,
) -> RemediationInputSnapshot:
    raw = RemediationInputSnapshot(
        finding=_finding_record(finding),
        applicability_result=applicability,
        gap_result=gap,
        requirements=planning_input.requirements,
        legal_evidence=planning_input.legal_evidence,
        relevant_product_facts=planning_input.relevant_product_facts,
        planner_request=planning_input.planner_request,
        product_twin_version_id=finding.product_twin_version_id,
    ).model_dump(mode="json")
    return RemediationInputSnapshot.model_validate(_sanitize(raw))


def _plan_type(plan: CodeChangePlan | DocumentChangePlan) -> RemediationType:
    return (
        RemediationType.CODE_CHANGE
        if isinstance(plan, CodeChangePlan)
        else RemediationType.DOCUMENT_CHANGE
    )


def _create_remediation(
    db: Session,
    *,
    planning_input: RemediationPlanningInput,
    plan: CodeChangePlan | DocumentChangePlan,
    title: str,
    summary: str,
    model_provider: str = "",
    model_name: str = "",
    prompt_version: str = "",
) -> RemediationRecord:
    """Persist a validated proposal and all canonical links atomically."""

    finding = _owned_finding(db, planning_input.tenant_id, planning_input.finding_id)
    if finding.status != "OPEN":
        raise RemediationConflictError(
            f"Cannot create remediation for Finding in {finding.status} status"
        )
    if not title.strip() or len(title) > 300 or not summary.strip():
        raise RemediationPersistenceError("Remediation title and summary are required")
    if _plan_type(plan) != planning_input.planner_request.remediation_type:
        raise RemediationPersistenceError("Plan type does not match planner request")

    linked_requirement_ids = set(_linked_requirement_ids(db, finding.id))
    requested_requirement_ids = {item.id for item in planning_input.requirements}
    unknown_requirements = requested_requirement_ids - linked_requirement_ids
    if unknown_requirements:
        raise RemediationGroundingError(
            f"Remediation references requirements outside the Finding: {sorted(unknown_requirements)}"
        )
    if not requested_requirement_ids:
        raise RemediationPersistenceError("Remediation requires canonical Requirement context")

    evidence_rows = list(
        db.scalars(
            select(FindingEvidence)
            .where(FindingEvidence.finding_id == finding.id)
            .order_by(FindingEvidence.id)
        ).all()
    )
    allowed_legal_unit_ids = {item.legal_unit_id for item in evidence_rows}
    requested_unit_ids = {item.legal_unit_id for item in planning_input.legal_evidence}
    unknown_units = requested_unit_ids - allowed_legal_unit_ids
    if unknown_units:
        raise RemediationGroundingError(
            f"Remediation references legal units outside the Finding: {sorted(unknown_units)}"
        )
    validate_remediation_grounding(plan, requested_requirement_ids, requested_unit_ids)

    gap = load_authoritative_gap_context(db, finding)
    applicability = _load_authoritative_applicability(db, finding, gap.requirement_id)
    _validate_planning_input(db, finding, planning_input, gap)
    if len(requested_requirement_ids) != len(planning_input.requirements):
        raise RemediationPersistenceError("Duplicate Requirement context is not allowed")
    if isinstance(plan, CodeChangePlan):
        if (
            plan.problem != finding.title
            or plan.current_state != gap.current_state
            or plan.required_state != gap.required_state
        ):
            raise RemediationPersistenceError(
                "Code change authoritative fields do not match the Finding and Gap"
            )
    elif (
        plan.issue != finding.title
        or plan.current_state != gap.current_state
        or plan.required_state != gap.required_state
    ):
        raise RemediationPersistenceError(
            "Document change authoritative fields do not match the Finding and Gap"
        )

    detail = load_finding(db, finding.tenant_id, finding.id)
    if detail is None:
        raise RemediationNotFoundError("Finding does not exist for this tenant")
    canonical_requirements = {item.id: item for item in detail.requirements}
    canonical_evidence = {item.legal_unit_id: item for item in detail.legal_evidence}
    for item in planning_input.requirements:
        canonical = canonical_requirements.get(item.id)
        if canonical is None:
            raise RemediationPersistenceError(f"Requirement {item.id} cannot be reloaded")
        if item.model_dump(mode="json") != canonical.model_dump(mode="json"):
            raise RemediationPersistenceError(
                f"Requirement {item.id} does not match canonical Finding context"
            )
    for item in planning_input.legal_evidence:
        canonical = canonical_evidence.get(item.legal_unit_id)
        if canonical is None:
            raise RemediationPersistenceError(
                f"Legal unit {item.legal_unit_id} cannot be reloaded"
            )
        if item.model_dump(mode="json") != canonical.model_dump(mode="json"):
            raise RemediationPersistenceError(
                f"Legal unit {item.legal_unit_id} does not match canonical Finding evidence"
            )

    if isinstance(plan, DocumentChangePlan):
        for reference in plan.evidence:
            canonical = canonical_evidence.get(reference.legal_unit_id)
            if canonical is None or reference.requirement_id not in canonical.requirement_ids:
                raise RemediationGroundingError(
                    "Document evidence reference is not linked to canonical Finding evidence"
                )
            expected_reference = RemediationEvidenceReference(
                requirement_id=reference.requirement_id,
                legal_unit_id=canonical.legal_unit_id,
                regulation_id=canonical.regulation_id,
                regulation_name=canonical.regulation_name,
                version_id=canonical.version_id,
                version=canonical.version,
                article=canonical.article,
                heading=canonical.heading,
                source_url=canonical.source_url,
            )
            if reference != expected_reference:
                raise RemediationGroundingError(
                    "Document evidence metadata does not match canonical Finding evidence"
                )

    if finding.product_twin_version_id is not None:
        twin = db.get(ProductTwinVersion, finding.product_twin_version_id)
        if twin is None or twin.product_id != finding.product_id:
            raise RemediationPersistenceError("Finding Product Twin version is invalid")

    snapshot = _build_input_snapshot(finding, planning_input, applicability, gap)
    row = Remediation(
        finding_id=finding.id,
        tenant_id=finding.tenant_id,
        product_id=finding.product_id,
        remediation_type=planning_input.planner_request.remediation_type.value,
        status=RemediationStatus.PROPOSED.value,
        title=title.strip(),
        summary=summary.strip(),
        plan_json=_sanitize(plan.model_dump(mode="json")),
        input_snapshot_json=_sanitize(snapshot.model_dump(mode="json")),
        product_twin_version_id=finding.product_twin_version_id,
        model_provider=model_provider,
        model_name=model_name,
        prompt_version=prompt_version,
    )
    try:
        db.add(row)
        db.flush()
        db.add_all(
            RemediationRequirement(remediation_id=row.id, requirement_id=requirement_id)
            for requirement_id in sorted(requested_requirement_ids)
        )
        for evidence in planning_input.legal_evidence:
            matching_rows = [
                item for item in evidence_rows
                if item.legal_unit_id == evidence.legal_unit_id
                and (item.requirement_id is None or item.requirement_id in requested_requirement_ids)
            ]
            if not matching_rows:
                raise RemediationGroundingError(
                    f"Legal unit {evidence.legal_unit_id} has no Finding evidence link"
                )
            for requirement_id in evidence.requirement_ids:
                if not any(
                    item.requirement_id in (None, requirement_id)
                    for item in matching_rows
                ):
                    raise RemediationGroundingError(
                        "Legal evidence Requirement/LegalUnit pair is not linked to the Finding"
                    )
            for finding_evidence in matching_rows:
                db.add(RemediationEvidence(
                    remediation_id=row.id,
                    legal_unit_id=evidence.legal_unit_id,
                    requirement_id=finding_evidence.requirement_id,
                    evidence_snapshot_json=_sanitize(evidence.model_dump(mode="json")),
                ))
        db.commit()
        db.refresh(row)
    except Exception:
        db.rollback()
        raise
    return _record(row)


def create_remediation(
    db: Session,
    *,
    planning_input: RemediationPlanningInput,
    plan: CodeChangePlan | DocumentChangePlan,
    title: str,
    summary: str,
    model_provider: str = "",
    model_name: str = "",
    prompt_version: str = "",
) -> RemediationRecord:
    """Run creation as one transaction, including all validation reads."""

    try:
        return _create_remediation(
            db,
            planning_input=planning_input,
            plan=plan,
            title=title,
            summary=summary,
            model_provider=model_provider,
            model_name=model_name,
            prompt_version=prompt_version,
        )
    except Exception:
        db.rollback()
        raise


def _record(row: Remediation) -> RemediationRecord:
    plan_type = CodeChangePlan if row.remediation_type == RemediationType.CODE_CHANGE.value else DocumentChangePlan
    return RemediationRecord(
        id=row.id,
        finding_id=row.finding_id,
        tenant_id=row.tenant_id,
        product_id=row.product_id,
        remediation_type=row.remediation_type,
        status=row.status,
        title=row.title,
        summary=row.summary,
        plan=plan_type.model_validate(row.plan_json),
        input_snapshot=RemediationInputSnapshot.model_validate(row.input_snapshot_json),
        product_twin_version_id=row.product_twin_version_id,
        model_provider=row.model_provider,
        model_name=row.model_name,
        prompt_version=row.prompt_version,
        decision_note=row.decision_note,
        decided_at=row.decided_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def list_remediations_for_finding(
    db: Session, tenant_id: int, finding_id: int
) -> list[RemediationListItem]:
    _owned_finding(db, tenant_id, finding_id)
    rows = db.scalars(
        select(Remediation)
        .where(Remediation.finding_id == finding_id, Remediation.tenant_id == tenant_id)
        .order_by(Remediation.created_at.desc(), Remediation.id.desc())
    ).all()
    return [RemediationListItem(
        id=row.id,
        finding_id=row.finding_id,
        tenant_id=row.tenant_id,
        product_id=row.product_id,
        remediation_type=row.remediation_type,
        status=row.status,
        title=row.title,
        summary=row.summary,
        product_twin_version_id=row.product_twin_version_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    ) for row in rows]


def get_remediation(
    db: Session, tenant_id: int, remediation_id: int
) -> RemediationDetail:
    row = _owned_remediation(db, tenant_id, remediation_id)
    finding_detail = load_finding(db, tenant_id, row.finding_id)
    if finding_detail is None:
        raise RemediationNotFoundError("Finding does not exist for this tenant")
    requirement_ids = list(
        db.scalars(
            select(RemediationRequirement.requirement_id)
            .where(RemediationRequirement.remediation_id == row.id)
            .order_by(RemediationRequirement.requirement_id)
        ).all()
    )
    requirements = load_requirement_contexts(db, requirement_ids)
    legal_unit_ids = set(
        db.scalars(
            select(RemediationEvidence.legal_unit_id)
            .where(RemediationEvidence.remediation_id == row.id)
        ).all()
    )
    legal_evidence = [
        item for item in load_legal_evidence(db, requirements)
        if item.legal_unit_id in legal_unit_ids
    ]
    evidence_by_unit = {item.legal_unit_id: item for item in legal_evidence}
    evidence_rows = db.scalars(
        select(RemediationEvidence)
        .where(RemediationEvidence.remediation_id == row.id)
        .order_by(RemediationEvidence.id)
    ).all()
    references = []
    for link in evidence_rows:
        evidence = evidence_by_unit.get(link.legal_unit_id)
        if evidence is None:
            raise RemediationPersistenceError(
                f"Remediation legal unit {link.legal_unit_id} cannot be canonically reloaded"
            )
        if link.requirement_id is not None:
            references.append(RemediationEvidenceReference(
                requirement_id=link.requirement_id,
                legal_unit_id=evidence.legal_unit_id,
                regulation_id=evidence.regulation_id,
                regulation_name=evidence.regulation_name,
                version_id=evidence.version_id,
                version=evidence.version,
                article=evidence.article,
                heading=evidence.heading,
                source_url=evidence.source_url,
            ))
    twin_reference = None
    if row.product_twin_version_id is not None:
        twin = db.get(ProductTwinVersion, row.product_twin_version_id)
        if twin is None:
            raise RemediationPersistenceError("Remediation Product Twin version cannot be reloaded")
        twin_reference = RemediationProductTwinVersionReference(
            id=twin.id, version_number=twin.version_number
        )
    return RemediationDetail(
        remediation=_record(row),
        finding=finding_detail.finding,
        requirements=requirements,
        legal_evidence=legal_evidence,
        evidence_references=references,
        product_twin_version=twin_reference,
    )


def _decide(
    db: Session,
    tenant_id: int,
    remediation_id: int,
    target: RemediationStatus,
    note: str | None,
) -> RemediationRecord:
    row = _owned_remediation(db, tenant_id, remediation_id)
    current = RemediationStatus(row.status)
    if current == target:
        return _record(row)
    if current != RemediationStatus.PROPOSED:
        raise RemediationConflictError(
            f"Cannot change remediation status from {current.value} to {target.value}"
        )
    row.status = target.value
    row.decision_note = note
    row.decided_at = _now()
    row.updated_at = _now()
    db.commit()
    db.refresh(row)
    return _record(row)


def approve_remediation(
    db: Session, tenant_id: int, remediation_id: int, *, note: str | None = None
) -> RemediationRecord:
    return _decide(db, tenant_id, remediation_id, RemediationStatus.APPROVED, note)


def reject_remediation(
    db: Session, tenant_id: int, remediation_id: int, *, note: str | None = None
) -> RemediationRecord:
    return _decide(db, tenant_id, remediation_id, RemediationStatus.REJECTED, note)
