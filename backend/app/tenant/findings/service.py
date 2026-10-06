"""Transactional persistence for Tenant Intelligence runs and findings."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Finding,
    FindingEvidence,
    FindingRequirement,
    LegalUnit,
    ProductTwinVersion,
    Requirement,
    TenantAgentRun,
    TenantMissingContextItem,
)
from app.tenant.applicability.schemas import MissingContextItem
from app.tenant.context.ownership import resolve_tenant_product
from app.tenant.context.schemas import ProductContext
from app.tenant.findings.schemas import (
    EvidenceSnapshot,
    FindingCandidate,
    FindingDetail,
    FindingEvidenceRecord,
    FindingRecord,
    TenantAgentInputSnapshot,
    TenantAgentOutputSnapshot,
    TenantAgentRunRecord,
    TenantAgentRunStatus,
    TenantTriggerType,
)
from app.tenant.gap.schemas import GapStatus
from app.tenant.regulatory.schemas import LegalEvidence, RegulationTrigger, RequirementContext
from app.tenant.regulatory.service import load_legal_evidence, load_requirement_contexts


class FindingPersistenceError(RuntimeError):
    pass


_FORBIDDEN_SNAPSHOT_KEYS = {
    "api_key", "llm_key", "authorization", "password", "secret", "token",
    "access_token", "refresh_token", "bearer",
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


def build_input_snapshot(
    product_context: ProductContext,
    trigger: RegulationTrigger,
    requirements: list[RequirementContext],
    legal_evidence: list[LegalEvidence],
) -> TenantAgentInputSnapshot:
    raw = TenantAgentInputSnapshot(
        tenant_id=product_context.tenant_id,
        product_id=product_context.product_id,
        product_twin_version_id=product_context.product_twin_version_id,
        product_context=product_context,
        trigger=trigger,
        requirements=requirements,
        legal_evidence=legal_evidence,
    ).model_dump(mode="json")
    return TenantAgentInputSnapshot.model_validate(_sanitize(raw))


def _owned_run(db: Session, run_id: int) -> TenantAgentRun:
    run = db.get(TenantAgentRun, run_id)
    if run is None:
        raise FindingPersistenceError(f"Tenant Agent run {run_id} does not exist")
    resolve_tenant_product(db, run.tenant_id, run.product_id)
    return run


def create_agent_run(
    db: Session,
    *,
    tenant_id: int,
    product_id: int,
    trigger_type: TenantTriggerType,
    trigger_id: str | None,
    input_snapshot: TenantAgentInputSnapshot,
    model_provider: str = "",
    model_name: str = "",
    prompt_version: str = "",
) -> TenantAgentRun:
    resolve_tenant_product(db, tenant_id, product_id)
    if input_snapshot.tenant_id != tenant_id or input_snapshot.product_id != product_id:
        raise FindingPersistenceError("Input snapshot tenant/product does not match the run")
    run = TenantAgentRun(
        tenant_id=tenant_id,
        product_id=product_id,
        trigger_type=trigger_type.value,
        trigger_id=trigger_id,
        status=TenantAgentRunStatus.PENDING.value,
        model_provider=model_provider,
        model_name=model_name,
        prompt_version=prompt_version,
        input_snapshot_json=_sanitize(input_snapshot.model_dump(mode="json")),
        output_json={},
        error="",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def mark_run_running(db: Session, run_id: int) -> TenantAgentRun:
    run = _owned_run(db, run_id)
    run.status = TenantAgentRunStatus.RUNNING.value
    run.started_at = run.started_at or _now()
    run.finished_at = None
    run.error = ""
    db.commit()
    db.refresh(run)
    return run


def mark_run_completed(
    db: Session, run_id: int, output: TenantAgentOutputSnapshot
) -> TenantAgentRun:
    run = _owned_run(db, run_id)
    run.status = TenantAgentRunStatus.COMPLETED.value
    run.output_json = output.model_copy(update={"status": TenantAgentRunStatus.COMPLETED}).model_dump(mode="json")
    run.finished_at = _now()
    run.error = ""
    db.commit()
    db.refresh(run)
    return run


def mark_run_failed(db: Session, run_id: int, error: str) -> TenantAgentRun:
    run = _owned_run(db, run_id)
    run.status = TenantAgentRunStatus.FAILED.value
    run.finished_at = _now()
    run.error = error[:4000]
    existing = dict(run.output_json or {})
    existing["status"] = TenantAgentRunStatus.FAILED.value
    run.output_json = existing
    db.commit()
    db.refresh(run)
    return run


def _validate_missing_requirements(db: Session, items: list[MissingContextItem]) -> None:
    for item in items:
        if item.requirement_id is not None and db.get(Requirement, item.requirement_id) is None:
            raise FindingPersistenceError(
                f"Missing context references unknown requirement {item.requirement_id}"
            )


def _add_missing_context(
    db: Session, run_id: int, items: list[MissingContextItem]
) -> list[TenantMissingContextItem]:
    _validate_missing_requirements(db, items)
    rows = [TenantMissingContextItem(
        run_id=run_id,
        requirement_id=item.requirement_id,
        field_path=item.field_path,
        question=item.question,
        reason=item.reason,
        status="OPEN",
    ) for item in items]
    db.add_all(rows)
    return rows


def persist_missing_context(
    db: Session, run_id: int, items: list[MissingContextItem]
) -> list[TenantMissingContextItem]:
    _owned_run(db, run_id)
    rows = _add_missing_context(db, run_id, items)
    db.commit()
    for row in rows:
        db.refresh(row)
    return rows


def mark_run_needs_user_input(
    db: Session,
    run_id: int,
    items: list[MissingContextItem],
    *,
    applicability_results=None,
) -> TenantAgentRun:
    run = _owned_run(db, run_id)
    try:
        _add_missing_context(db, run_id, items)
        output = TenantAgentOutputSnapshot(
            applicability_results=applicability_results or [],
            gap_results=[],
            finding_ids=[],
            missing_context=items,
            status=TenantAgentRunStatus.NEEDS_USER_INPUT,
        )
        run.status = TenantAgentRunStatus.NEEDS_USER_INPUT.value
        run.output_json = output.model_dump(mode="json")
        run.finished_at = _now()
        run.error = ""
        db.commit()
        db.refresh(run)
        return run
    except Exception:
        db.rollback()
        raise


def _eligible(candidate: FindingCandidate) -> bool:
    return (
        candidate.applicability.applies is True
        and candidate.gap is not None
        and candidate.gap.gap_status in {GapStatus.POTENTIAL, GapStatus.CONFIRMED}
    )


def _validate_twin(db: Session, product_id: int, version_id: int | None) -> None:
    if version_id is None:
        return
    version = db.get(ProductTwinVersion, version_id)
    if version is None or version.product_id != product_id:
        raise FindingPersistenceError("Finding references an invalid Product Twin version")


def _persist_candidate(
    db: Session, run: TenantAgentRun, candidate: FindingCandidate
) -> Finding:
    assert candidate.gap is not None
    _validate_twin(db, run.product_id, candidate.product_twin_version_id)
    requirement_ids = list(dict.fromkeys(item.id for item in candidate.requirements))
    if candidate.applicability.requirement_id not in requirement_ids:
        raise FindingPersistenceError(
            "Finding applicability result has no canonical Requirement link"
        )
    if candidate.gap.requirement_id not in requirement_ids:
        raise FindingPersistenceError("Finding gap result has no canonical Requirement link")
    for requirement_id in requirement_ids:
        if db.get(Requirement, requirement_id) is None:
            raise FindingPersistenceError(f"Finding references unknown requirement {requirement_id}")

    finding = Finding(
        run_id=run.id,
        tenant_id=run.tenant_id,
        product_id=run.product_id,
        trigger_type=run.trigger_type,
        trigger_id=run.trigger_id,
        title=candidate.title,
        status="OPEN",
        impact_level=candidate.impact_level.value,
        confidence=candidate.confidence,
        applicability_summary=candidate.applicability.reasoning_summary,
        gap_status=candidate.gap.gap_status.value,
        gap_type=candidate.gap.gap_type.value,
        gap_summary=candidate.gap.reasoning_summary,
        product_twin_version_id=candidate.product_twin_version_id,
    )
    db.add(finding)
    db.flush()
    db.add_all([
        FindingRequirement(finding_id=finding.id, requirement_id=requirement_id)
        for requirement_id in requirement_ids
    ])

    for evidence in candidate.legal_evidence:
        unit = db.get(LegalUnit, evidence.legal_unit_id)
        if unit is None:
            raise FindingPersistenceError(
                f"Finding evidence references unknown legal unit {evidence.legal_unit_id}"
            )
        if unit.version_id != evidence.version_id:
            raise FindingPersistenceError(
                f"Finding evidence version conflicts for legal unit {evidence.legal_unit_id}"
            )
        linked_requirements = [item for item in evidence.requirement_ids if item in requirement_ids]
        for requirement_id in linked_requirements or [None]:
            db.add(FindingEvidence(
                finding_id=finding.id,
                legal_unit_id=evidence.legal_unit_id,
                requirement_id=requirement_id,
                evidence_snapshot_json=evidence.model_dump(mode="json"),
            ))
    return finding


def persist_findings(
    db: Session,
    run_id: int,
    candidates: list[FindingCandidate],
    *,
    missing_context: list[MissingContextItem] | None = None,
) -> list[Finding]:
    run = _owned_run(db, run_id)
    derived_missing = [
        item
        for candidate in candidates
        if candidate.applicability.applies is None
        for item in candidate.applicability.missing_context
    ]
    combined_missing = [*(missing_context or []), *derived_missing]
    missing_context = list({
        (item.requirement_id, item.field_path, item.question, item.reason): item
        for item in combined_missing
    }.values())
    try:
        findings = [_persist_candidate(db, run, candidate) for candidate in candidates if _eligible(candidate)]
        _add_missing_context(db, run_id, missing_context)
        db.flush()
        status = (
            TenantAgentRunStatus.NEEDS_USER_INPUT
            if missing_context else TenantAgentRunStatus.COMPLETED
        )
        output = TenantAgentOutputSnapshot(
            applicability_results=[item.applicability for item in candidates],
            gap_results=[item.gap for item in candidates if item.gap is not None],
            finding_ids=[item.id for item in findings],
            missing_context=missing_context,
            status=status,
        )
        run.status = status.value
        run.output_json = output.model_dump(mode="json")
        run.finished_at = _now()
        run.error = ""
        db.commit()
        for finding in findings:
            db.refresh(finding)
        return findings
    except Exception as exc:
        db.rollback()
        mark_run_failed(db, run_id, str(exc))
        raise FindingPersistenceError(str(exc)) from exc


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


def _run_record(row: TenantAgentRun) -> TenantAgentRunRecord:
    return TenantAgentRunRecord(
        id=row.id,
        tenant_id=row.tenant_id,
        product_id=row.product_id,
        trigger_type=row.trigger_type,
        trigger_id=row.trigger_id,
        status=row.status,
        model_provider=row.model_provider,
        model_name=row.model_name,
        prompt_version=row.prompt_version,
        input_snapshot=row.input_snapshot_json,
        output=row.output_json,
        started_at=row.started_at,
        finished_at=row.finished_at,
        error=row.error,
        created_at=row.created_at,
    )


def load_finding(db: Session, tenant_id: int, finding_id: int) -> FindingDetail | None:
    finding = db.get(Finding, finding_id)
    if finding is None:
        return None
    if finding.tenant_id != tenant_id:
        return None
    resolve_tenant_product(db, tenant_id, finding.product_id)
    run = db.get(TenantAgentRun, finding.run_id)
    if run is None:
        raise FindingPersistenceError("Finding has no canonical Tenant Agent run")
    requirement_ids = list(db.scalars(
        select(FindingRequirement.requirement_id)
        .where(FindingRequirement.finding_id == finding.id)
        .order_by(FindingRequirement.requirement_id)
    ).all())
    requirements = load_requirement_contexts(db, requirement_ids)
    canonical_evidence = load_legal_evidence(db, requirements)
    evidence_rows = db.scalars(
        select(FindingEvidence)
        .where(FindingEvidence.finding_id == finding.id)
        .order_by(FindingEvidence.id)
    ).all()
    snapshots = [FindingEvidenceRecord(
        id=row.id,
        finding_id=row.finding_id,
        legal_unit_id=row.legal_unit_id,
        requirement_id=row.requirement_id,
        snapshot=EvidenceSnapshot.model_validate(row.evidence_snapshot_json),
        created_at=row.created_at,
    ) for row in evidence_rows]
    return FindingDetail(
        finding=_finding_record(finding),
        run=_run_record(run),
        requirements=requirements,
        legal_evidence=canonical_evidence,
        evidence_snapshots=snapshots,
    )
