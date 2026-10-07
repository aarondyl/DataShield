"""Stable service facade over Global Regulatory Intelligence internals.

Tenant consumers use these functions and existing response DTOs instead of
depending on ORM rows, vector stores, embeddings, or pgvector directly.
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    LegalUnit,
    Regulation,
    RegulationChange,
    RegulationEvent,
    RegulationVersion,
    Requirement,
)
from app.rag.embeddings import embed_texts_with_fallback
from app.regintel.retrieval import get_legal_chunk_store
from app.schemas.regintel import (
    ChangeOut,
    EventOut,
    LegalSearchResultItem,
    LegalUnitOut,
    RegulationInfoOut,
    RequirementOut,
    VersionOut,
)


def get_regulation_event(db: Session, event_id: str) -> EventOut | None:
    row = db.scalar(select(RegulationEvent).where(RegulationEvent.event_id == event_id))
    return EventOut.model_validate(row) if row else None


def get_regulation_change(db: Session, change_id: int) -> ChangeOut | None:
    row = db.get(RegulationChange, change_id)
    if row is None:
        return None
    regulation = db.get(Regulation, row.regulation_id)
    unit = db.get(LegalUnit, row.legal_unit_id) if row.legal_unit_id else None
    out = ChangeOut.model_validate(row)
    if regulation:
        out.regulation_name = regulation.name
        out.source_url = regulation.canonical_source_url or regulation.source_url
    if unit:
        out.article = unit.unit_number
    return out


def list_regulation_changes(
    db: Session, *, regulation_id: int, version_id: int
) -> list[ChangeOut]:
    rows = db.scalars(
        select(RegulationChange)
        .where(
            RegulationChange.regulation_id == regulation_id,
            RegulationChange.to_version_id == version_id,
        )
        .order_by(RegulationChange.id)
    ).all()
    return [item for row in rows if (item := get_regulation_change(db, row.id)) is not None]


def get_regulation_info(db: Session, regulation_id: int) -> RegulationInfoOut | None:
    row = db.get(Regulation, regulation_id)
    return RegulationInfoOut.model_validate(row) if row else None


def get_regulation_version(db: Session, version_id: int) -> VersionOut | None:
    row = db.get(RegulationVersion, version_id)
    return VersionOut.model_validate(row) if row else None


def load_requirements(db: Session, requirement_ids: Iterable[int]) -> list[RequirementOut]:
    ids = list(dict.fromkeys(requirement_ids))
    if not ids:
        return []
    rows = db.scalars(select(Requirement).where(Requirement.id.in_(ids))).all()
    by_id = {row.id: row for row in rows}
    return [RequirementOut.model_validate(by_id[item]) for item in ids if item in by_id]


def load_requirements_for_legal_units(
    db: Session, legal_unit_ids: Iterable[int]
) -> list[RequirementOut]:
    ids = list(dict.fromkeys(legal_unit_ids))
    if not ids:
        return []
    rows = db.scalars(
        select(Requirement).where(Requirement.legal_unit_id.in_(ids)).order_by(Requirement.id)
    ).all()
    return [RequirementOut.model_validate(row) for row in rows]


def load_legal_units(db: Session, legal_unit_ids: Iterable[int]) -> list[LegalUnitOut]:
    ids = list(dict.fromkeys(legal_unit_ids))
    if not ids:
        return []
    rows = db.scalars(select(LegalUnit).where(LegalUnit.id.in_(ids))).all()
    by_id = {row.id: row for row in rows}
    results: list[LegalUnitOut] = []
    for unit_id in ids:
        unit = by_id.get(unit_id)
        if unit is None:
            continue
        version = db.get(RegulationVersion, unit.version_id)
        regulation = db.get(Regulation, version.regulation_id) if version else None
        out = LegalUnitOut.model_validate(unit)
        if version:
            out.version_number = version.version_number
        if regulation:
            out.regulation_id = regulation.id
            out.regulation_name = regulation.name
            out.official_source_url = regulation.canonical_source_url or regulation.source_url
            out.is_current_version = regulation.current_version_id == unit.version_id
        results.append(out)
    return results


def search_legal_requirements(
    db: Session,
    query: str,
    *,
    regulation_ids: list[int] | None = None,
    top_k: int = 8,
) -> list[RequirementOut]:
    """Search current legal chunks and return referenced Requirement DTOs."""

    if not query.strip():
        return []
    query_embedding = embed_texts_with_fallback([query])[0]
    hits = get_legal_chunk_store().search(
        query_embedding,
        top_k=top_k,
        regulation_ids=regulation_ids,
        current_only=True,
    )
    requirement_ids: list[int] = []
    for hit in hits:
        legal_unit_id = hit.get("legal_unit_id")
        if legal_unit_id is None:
            continue
        rows = db.scalars(
            select(Requirement).where(
                Requirement.legal_unit_id == legal_unit_id,
                Requirement.status != "SUPERSEDED",
            )
        ).all()
        requirement_ids.extend(row.id for row in rows)
    return load_requirements(db, requirement_ids)


__all__ = [
    "ChangeOut",
    "EventOut",
    "LegalSearchResultItem",
    "LegalUnitOut",
    "RegulationInfoOut",
    "RequirementOut",
    "VersionOut",
    "get_regulation_change",
    "get_regulation_event",
    "get_regulation_info",
    "get_regulation_version",
    "list_regulation_changes",
    "load_legal_units",
    "load_requirements",
    "load_requirements_for_legal_units",
    "search_legal_requirements",
]
