"""Build tenant-facing regulatory contexts through the regintel facade only."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.regintel.service import (
    ChangeOut,
    RequirementOut,
    get_regulation_change,
    get_regulation_event,
    get_regulation_info,
    get_regulation_version,
    list_regulation_changes,
    load_legal_units,
    load_requirements,
    load_requirements_for_legal_units,
    search_legal_requirements,
)
from app.tenant.regulatory.schemas import (
    LegalEvidence,
    ManualScanContext,
    RegulationSourceContext,
    RegulationTrigger,
    RequirementContext,
)


_SUPPORTED_EVENT = "regulation.change.ready"
_MATERIALITY = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


class RegulatoryContextError(ValueError):
    pass


class RegulationTriggerNotFoundError(RegulatoryContextError):
    pass


class UnsupportedRegulationEventError(RegulatoryContextError):
    pass


class TriggerDataConflictError(RegulatoryContextError):
    pass


class InvalidRegulationTriggerError(RegulatoryContextError):
    pass


def _int_list(value, field: str) -> list[int]:
    if value is None:
        return []
    if not isinstance(value, list) or any(isinstance(item, bool) or not isinstance(item, int) for item in value):
        raise InvalidRegulationTriggerError(f"Event payload field {field} must be a list of integers")
    return list(dict.fromkeys(value))


def _str_list(value, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise InvalidRegulationTriggerError(f"Event payload field {field} must be a list of strings")
    return list(dict.fromkeys(value))


def _authoritative_id(payload: dict, field: str, database_value: int | None) -> int | None:
    payload_value = payload.get(field)
    if payload_value is not None and (isinstance(payload_value, bool) or not isinstance(payload_value, int)):
        raise InvalidRegulationTriggerError(f"Event payload field {field} must be an integer")
    if database_value is not None and payload_value is not None and database_value != payload_value:
        raise TriggerDataConflictError(
            f"Event payload {field}={payload_value} conflicts with database value {database_value}"
        )
    return database_value if database_value is not None else payload_value


def _highest_materiality(changes: list[ChangeOut], payload_value: object) -> str:
    values = [change.materiality for change in changes]
    if isinstance(payload_value, str):
        if payload_value not in _MATERIALITY:
            raise InvalidRegulationTriggerError(
                f"Unsupported event materiality: {payload_value}"
            )
        values.append(payload_value)
    return max(values or ["LOW"], key=lambda item: _MATERIALITY.get(item, 0))


def load_regulation_trigger(db: Session, event_id: str) -> RegulationTrigger:
    event = get_regulation_event(db, event_id)
    if event is None:
        raise RegulationTriggerNotFoundError(f"Regulation event {event_id} does not exist")
    if event.event_type != _SUPPORTED_EVENT:
        raise UnsupportedRegulationEventError(
            f"Unsupported regulation event type: {event.event_type}"
        )
    payload = dict(event.payload or {})
    if payload.get("event_id") not in (None, event.event_id):
        raise TriggerDataConflictError("Event payload event_id conflicts with database value")
    if payload.get("event_type") not in (None, event.event_type):
        raise TriggerDataConflictError("Event payload event_type conflicts with database value")

    regulation_id = _authoritative_id(payload, "regulation_id", event.regulation_id)
    version_id = _authoritative_id(payload, "version_id", event.version_id)
    if regulation_id is None or version_id is None:
        raise InvalidRegulationTriggerError("Regulation event must resolve regulation_id and version_id")

    regulation = get_regulation_info(db, regulation_id)
    version = get_regulation_version(db, version_id)
    if regulation is None or version is None:
        raise InvalidRegulationTriggerError("Regulation event references missing regulation or version")
    if version.regulation_id != regulation_id:
        raise TriggerDataConflictError("Event version does not belong to the event regulation")

    change_ids = _int_list(payload.get("change_ids"), "change_ids")
    if change_ids:
        changes = []
        for change_id in change_ids:
            change = get_regulation_change(db, change_id)
            if change is None:
                raise InvalidRegulationTriggerError(f"Regulation change {change_id} does not exist")
            changes.append(change)
    else:
        changes = list_regulation_changes(
            db, regulation_id=regulation_id, version_id=version_id
        )
        change_ids = [change.id for change in changes]

    for change in changes:
        if change.regulation_id != regulation_id or change.to_version_id != version_id:
            raise TriggerDataConflictError(
                f"Regulation change {change.id} conflicts with event regulation/version"
            )

    payload_requirement_ids = _int_list(payload.get("requirement_ids"), "requirement_ids")
    change_requirement_ids = [
        item for change in changes for item in _int_list(change.requirement_ids, "requirement_ids")
    ]
    requirement_ids = list(dict.fromkeys(payload_requirement_ids or change_requirement_ids))
    payload_unit_ids = _int_list(payload.get("affected_legal_unit_ids"), "affected_legal_unit_ids")
    change_unit_ids = [change.legal_unit_id for change in changes if change.legal_unit_id is not None]
    legal_unit_ids = list(dict.fromkeys(payload_unit_ids or change_unit_ids))

    return RegulationTrigger(
        event_id=event.event_id,
        event_type=event.event_type,
        regulation_id=regulation_id,
        version_id=version_id,
        change_id=change_ids[0] if change_ids else None,
        change_ids=change_ids,
        materiality=_highest_materiality(changes, payload.get("materiality")),
        topics=_str_list(payload.get("topics"), "topics"),
        requirement_ids=requirement_ids,
        legal_unit_ids=legal_unit_ids,
        change_summaries=[change.semantic_summary for change in changes if change.semantic_summary],
        payload=payload,
        source=RegulationSourceContext(
            regulation_name=regulation.name,
            jurisdiction=regulation.jurisdiction,
            version=version.version_number,
            source_url=regulation.canonical_source_url or regulation.source_url,
            effective_date=version.effective_from,
            review_status=version.review_status,
        ),
    )


def _requirement_context(db: Session, item: RequirementOut) -> RequirementContext:
    regulation = get_regulation_info(db, item.regulation_id)
    version = get_regulation_version(db, item.version_id)
    return RequirementContext(
        **item.model_dump(exclude={"created_at"}),
        regulation_name=regulation.name if regulation else "",
        jurisdiction=regulation.jurisdiction if regulation else "",
        regulation_version=version.version_number if version else None,
        source_url=(regulation.canonical_source_url or regulation.source_url) if regulation else "",
        review_status=version.review_status if version else "UNREVIEWED",
    )


def load_requirement_contexts(
    db: Session, requirement_ids: list[int]
) -> list[RequirementContext]:
    """Load canonical Requirement rows as tenant-facing DTOs."""

    return [_requirement_context(db, item) for item in load_requirements(db, requirement_ids)]


def resolve_requirements_for_manual_scan(
    db: Session, scan: ManualScanContext
) -> list[RequirementContext]:
    """Resolve explicit ids first, then use the regintel search facade."""

    if scan.requirement_ids:
        items = load_requirements(db, scan.requirement_ids)
        loaded_ids = {item.id for item in items}
        missing_ids = [item for item in scan.requirement_ids if item not in loaded_ids]
        if missing_ids:
            raise InvalidRegulationTriggerError(
                f"Manual scan references missing requirements: {missing_ids}"
            )
    elif scan.query.strip():
        items = search_legal_requirements(
            db,
            scan.query,
            regulation_ids=[scan.regulation_id] if scan.regulation_id else None,
        )
    else:
        items = []
    return [_requirement_context(db, item) for item in items]


def resolve_requirements_for_trigger(
    db: Session, trigger: RegulationTrigger
) -> list[RequirementContext]:
    items = load_requirements(db, trigger.requirement_ids) if trigger.requirement_ids else []
    if trigger.requirement_ids:
        loaded_ids = {item.id for item in items}
        missing_ids = [item for item in trigger.requirement_ids if item not in loaded_ids]
        if missing_ids:
            raise InvalidRegulationTriggerError(
                f"Regulation event references missing requirements: {missing_ids}"
            )
    if not items:
        changes = [
            change for change_id in trigger.change_ids
            if (change := get_regulation_change(db, change_id)) is not None
        ]
        change_ids = list(dict.fromkeys(
            requirement_id
            for change in changes
            for requirement_id in change.requirement_ids
        ))
        items = load_requirements(db, change_ids)
    if not items and trigger.legal_unit_ids:
        items = load_requirements_for_legal_units(db, trigger.legal_unit_ids)
    if not items:
        query_parts = [*trigger.change_summaries, *trigger.topics]
        if trigger.legal_unit_ids:
            query_parts.extend(
                unit.text for unit in load_legal_units(db, trigger.legal_unit_ids) if unit.text
            )
        query = " ".join(query_parts).strip()
        items = search_legal_requirements(
            db,
            query,
            regulation_ids=[trigger.regulation_id],
        )
    return [_requirement_context(db, item) for item in items]


def load_legal_evidence(
    db: Session, requirements: list[RequirementContext]
) -> list[LegalEvidence]:
    requirement_ids_by_unit: dict[int, list[int]] = {}
    for item in requirements:
        if item.legal_unit_id is not None:
            requirement_ids_by_unit.setdefault(item.legal_unit_id, []).append(item.id)
    units = load_legal_units(db, requirement_ids_by_unit)
    loaded_unit_ids = {unit.id for unit in units}
    missing_unit_ids = [item for item in requirement_ids_by_unit if item not in loaded_unit_ids]
    if missing_unit_ids:
        raise InvalidRegulationTriggerError(
            f"Requirements reference missing legal units: {missing_unit_ids}"
        )
    evidence: list[LegalEvidence] = []
    for unit in units:
        version = get_regulation_version(db, unit.version_id)
        if version is None:
            raise InvalidRegulationTriggerError(
                f"Legal unit {unit.id} references missing version {unit.version_id}"
            )
        evidence.append(LegalEvidence(
            legal_unit_id=unit.id,
            regulation_id=unit.regulation_id,
            regulation_name=unit.regulation_name,
            version_id=unit.version_id,
            version=unit.version_number,
            article=unit.unit_number,
            heading=unit.heading,
            content=unit.text,
            source_url=unit.official_source_url,
            effective_date=version.effective_from,
            requirement_ids=requirement_ids_by_unit[unit.id],
            review_status=version.review_status,
        ))
    return evidence
