"""Versioned product observations. No legal conclusions or Product field mutation."""

import hashlib
import json
from collections import defaultdict

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Product, ProductTwinAnalysisRef, ProductTwinDecision, ProductTwinFact, ProductTwinVersion
from app.understanding.schemas import AnalysisJob, Fact, FindingStatus


def _latest(db: Session, product_id: int) -> ProductTwinVersion | None:
    return db.scalar(select(ProductTwinVersion).where(ProductTwinVersion.product_id == product_id)
                     .order_by(ProductTwinVersion.version_number.desc()).limit(1))


def _facts(db: Session, version_id: int) -> list[ProductTwinFact]:
    return list(db.scalars(select(ProductTwinFact).where(ProductTwinFact.version_id == version_id)
                           .order_by(ProductTwinFact.id)).all())


def _new_version(db: Session, product_id: int, reason: str,
                 source_analysis_id: str | None = None) -> tuple[ProductTwinVersion, list[ProductTwinFact]]:
    # Serializes version assignment on PostgreSQL; the unique key also guards it.
    db.execute(select(Product.id).where(Product.id == product_id).with_for_update()).scalar_one()
    previous = _latest(db, product_id)
    version = ProductTwinVersion(product_id=product_id, version_number=previous.version_number + 1 if previous else 1,
                                 reason=reason, source_analysis_id=source_analysis_id)
    db.add(version)
    db.flush()
    copies = []
    if previous:
        for fact in _facts(db, previous.id):
            copy = ProductTwinFact(version_id=version.id, group_name=fact.group_name, name=fact.name,
                                   status=fact.status, confidence=fact.confidence, source_kind=fact.source_kind,
                                   analysis_id=fact.analysis_id, evidence=fact.evidence, scan_scope=fact.scan_scope,
                                   confirmation_status=fact.confirmation_status,
                                   supersedes_fact_id=fact.supersedes_fact_id)
            db.add(copy)
            copies.append(copy)
        db.flush()
    return version, copies


def _scope(result, kind: str) -> dict:
    common = {"coverage_complete": result.coverage_complete, "limitations": result.limitations}
    if kind == "repository":
        return {**common, "analysis_mode": result.analysis_mode.value, "files_scanned": result.files_scanned}
    return {**common, "url": result.url, "pages_analyzed": result.pages_analyzed}


def _observations(result, kind: str):
    for group in ("features", "data_types", "vendors"):
        for fact in getattr(result, group):
            yield group, fact
    for fact in result.capabilities.values():
        yield "capabilities", fact
    if kind == "repository":
        for fact in result.stack_facts:
            yield "stack", fact
    else:
        if result.product_category_fact:
            yield "product_category", result.product_category_fact
        for item in result.target_users:
            yield "target_users", Fact(name=item.type, status=FindingStatus.PARTIAL,
                                       confidence=item.confidence, evidence_ids=item.evidence_ids)
        for item in result.market_clues:
            yield "market_clues", Fact(name=item.jurisdiction, status=FindingStatus.PARTIAL,
                                        confidence=item.confidence, evidence_ids=item.evidence_ids)
        for name, item in result.public_documents.items():
            yield "public_documents", Fact(name=name, status=item.status, confidence=item.confidence,
                                            evidence_ids=item.evidence_ids)


def attach_analysis(db: Session, product_id: int, job: AnalysisJob) -> ProductTwinVersion:
    if job.product_id != product_id:
        raise HTTPException(404, "Analysis is not linked to this product")
    if job.status != "COMPLETED":
        raise HTTPException(409, "Only completed analyses can be attached")
    db.execute(select(Product.id).where(Product.id == product_id).with_for_update()).scalar_one()
    if db.get(ProductTwinAnalysisRef, job.analysis_id):
        raise HTTPException(409, "Analysis is already attached")
    result = job.repository_analysis if job.kind == "repository" else job.website_analysis
    if result is None:
        raise HTTPException(409, "Completed analysis has no result")
    evidence = {item.evidence_id: item for item in result.evidence}
    observations = list(_observations(result, job.kind))
    for _, fact in observations:
        if any(eid not in evidence for eid in fact.evidence_ids):
            raise HTTPException(422, "Analysis contains an unresolved evidence reference")
    scope = _scope(result, job.kind)
    result_json = result.model_dump(mode="json")
    digest = hashlib.sha256(json.dumps(result_json, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    ref = ProductTwinAnalysisRef(analysis_id=job.analysis_id, product_id=product_id, kind=job.kind,
                                 result=result_json, result_sha256=digest, scan_scope=scope)
    db.add(ref)
    version, _ = _new_version(db, product_id, "ANALYSIS_ATTACHED", job.analysis_id)
    for group, fact in observations:
        snapshots = []
        for eid in fact.evidence_ids:
            item = evidence[eid].model_dump(mode="json")
            item["evidence_id"] = f"{job.analysis_id}:{eid}"
            snapshots.append(item)
        db.add(ProductTwinFact(version_id=version.id, group_name=group, name=fact.name,
                               status=fact.status.value, confidence=fact.confidence, source_kind=job.kind.upper(),
                               analysis_id=job.analysis_id, evidence=snapshots, scan_scope=scope,
                               confirmation_status="UNREVIEWED"))
    db.commit()
    db.refresh(version)
    return version


def add_manual_fact(db: Session, product_id: int, group: str, fact: Fact, note: str) -> ProductTwinVersion:
    version, _ = _new_version(db, product_id, "MANUAL_FACT")
    db.add(ProductTwinFact(version_id=version.id, group_name=group, name=fact.name,
                           status=fact.status.value, confidence=fact.confidence, source_kind="USER",
                           analysis_id=None, evidence=[{"evidence_id": f"manual:{version.id}",
                                                         "type": "USER_DESCRIPTION", "reason": note}],
                           scan_scope={"type": "user_input"}, confirmation_status="CONFIRMED"))
    db.commit()
    db.refresh(version)
    return version


def decide_fact(db: Session, product_id: int, fact_id: int, action: str, note: str,
                actor_label: str, correction: Fact | None = None) -> ProductTwinVersion:
    db.execute(select(Product.id).where(Product.id == product_id).with_for_update()).scalar_one()
    current = _latest(db, product_id)
    if current is None:
        raise HTTPException(404, "Product Twin has no facts")
    original = db.get(ProductTwinFact, fact_id)
    if original is None or original.version_id != current.id:
        raise HTTPException(409, "Fact is not in the current version")
    if original.confirmation_status == "CORRECTED" or (action == "CONFIRM" and original.confirmation_status == "CONFIRMED"):
        raise HTTPException(409, "Fact has already been decided")
    if action == "CORRECT" and correction is None:
        raise HTTPException(422, "Correction fact is required")
    position = next(i for i, fact in enumerate(_facts(db, current.id)) if fact.id == fact_id)
    version, copies = _new_version(db, product_id, action)
    selected = copies[position]
    if action == "CONFIRM":
        selected.confirmation_status = "CONFIRMED"
        decision_fact = selected
    else:
        selected.confirmation_status = "CORRECTED"
        decision_fact = ProductTwinFact(version_id=version.id, group_name=original.group_name,
                                        name=correction.name, status=correction.status.value,
                                        confidence=correction.confidence, source_kind="USER", analysis_id=None,
                                        evidence=[{"evidence_id": f"manual:{version.id}:{fact_id}",
                                                   "type": "USER_DESCRIPTION", "reason": note}],
                                        scan_scope={"type": "user_correction"}, confirmation_status="CONFIRMED",
                                        supersedes_fact_id=fact_id)
        db.add(decision_fact)
    db.flush()
    db.add(ProductTwinDecision(product_id=product_id, version_id=version.id, fact_id=decision_fact.id,
                               action=action, note=note, actor_label=actor_label))
    db.commit()
    db.refresh(version)
    return version


def version_view(db: Session, version: ProductTwinVersion) -> dict:
    facts = _facts(db, version.id)
    grouped = defaultdict(list)
    for fact in facts:
        canonical_name = "user_registration" if fact.group_name == "features" and fact.name == "signup" else fact.name
        grouped[(fact.group_name, canonical_name)].append(fact)
    conflicts = []
    for (group, name), candidates in grouped.items():
        active = [f for f in candidates if f.confirmation_status != "CORRECTED" and f.status != "UNKNOWN"]
        if len({f.status for f in active}) > 1 and len({f.source_kind for f in active}) > 1:
            conflicts.append({"group": group, "name": name, "fact_ids": [f.id for f in active],
                              "statuses": [f.status for f in active]})
    decisions = list(db.scalars(select(ProductTwinDecision).where(ProductTwinDecision.product_id == version.product_id,
                          ProductTwinDecision.version_id == version.id).order_by(ProductTwinDecision.id)).all())
    return {"product_id": version.product_id, "version": version.version_number, "reason": version.reason,
            "source_analysis_id": version.source_analysis_id,
            "created_at": version.created_at, "facts": [{"id": f.id, "group": f.group_name, "name": f.name,
            "status": f.status, "confidence": f.confidence, "source_kind": f.source_kind, "analysis_id": f.analysis_id,
            "evidence": f.evidence, "scan_scope": f.scan_scope, "confirmation_status": f.confirmation_status,
            "supersedes_fact_id": f.supersedes_fact_id} for f in facts],
            "conflicts": conflicts,
            "decisions": [{"id": d.id, "fact_id": d.fact_id, "action": d.action, "note": d.note,
                           "actor_label": d.actor_label, "created_at": d.created_at} for d in decisions]}


def current_view(db: Session, product_id: int) -> dict:
    version = _latest(db, product_id)
    if version is None:
        return {"product_id": product_id, "version": 0, "facts": [], "conflicts": [], "decisions": []}
    return version_view(db, version)
