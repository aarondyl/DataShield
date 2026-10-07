"""Regintel facade and tenant regulatory context resolution."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models import (
    LegalUnit,
    Regulation,
    RegulationChange,
    RegulationEvent,
    RegulationVersion,
    Requirement,
)
from app.schemas.regintel import RequirementOut
from app.tenant.regulatory import (
    InvalidRegulationTriggerError,
    TriggerDataConflictError,
    UnsupportedRegulationEventError,
    load_legal_evidence,
    load_regulation_trigger,
    resolve_requirements_for_trigger,
)


@pytest.fixture
def regulatory_db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'tenant-regulatory.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        regulation = Regulation(id=1, name="EU Test Act", jurisdiction="EU",
                                canonical_source_url="https://example.eu/official")
        db.add(regulation)
        db.flush()
        version = RegulationVersion(id=1, regulation_id=1, version_number=2,
                                    normalized_text="Article 1 transparency", content_hash="a" * 64,
                                    is_current=True)
        db.add(version)
        db.flush()
        regulation.current_version_id = version.id
        unit = LegalUnit(id=1, version_id=1, unit_type="article", unit_number="Article 1",
                         heading="Transparency", text="Providers shall publish transparency information.")
        db.add(unit)
        db.flush()
        requirement = Requirement(
            id=1, regulation_id=1, version_id=1, legal_unit_id=1,
            requirement_type="obligation", subject_type="provider", action_type="inform",
            object_type="AI system", conditions_json=[{"market": "EU"}], exceptions_json=[],
            summary="Publish transparency information", confidence=.65, status="NEEDS_REVIEW",
        )
        db.add(requirement)
        db.flush()
        change = RegulationChange(
            id=1, regulation_id=1, to_version_id=1, legal_unit_id=1, change_type="ADDED",
            semantic_summary="A new transparency duty was added", materiality="HIGH",
            requirement_ids=[1],
        )
        db.add(change)
        db.flush()
        db.add(RegulationEvent(
            event_id="evt_full", event_type="regulation.change.ready", regulation_id=1,
            version_id=1, payload={
                "event_id": "evt_full", "event_type": "regulation.change.ready",
                "regulation_id": 1, "version_id": 1, "change_ids": [1],
                "requirement_ids": [1], "affected_legal_unit_ids": [1],
                "topics": ["透明度"], "materiality": "HIGH",
            },
        ))
        db.commit()
        yield db


def test_event_requirement_and_legal_evidence_are_stable_dtos(regulatory_db):
    trigger = load_regulation_trigger(regulatory_db, "evt_full")
    requirements = resolve_requirements_for_trigger(regulatory_db, trigger)
    evidence = load_legal_evidence(regulatory_db, requirements)

    assert trigger.event_id == "evt_full"
    assert trigger.change_id == 1
    assert trigger.requirement_ids == [1]
    assert trigger.source.version == 2
    assert requirements[0].status == "NEEDS_REVIEW"
    assert requirements[0].conditions == [{"market": "EU"}]
    assert requirements[0].regulation_name == "EU Test Act"
    assert evidence[0].legal_unit_id == 1
    assert evidence[0].requirement_ids == [1]
    assert evidence[0].article == "Article 1"
    assert evidence[0].version == 2
    assert evidence[0].source_url == "https://example.eu/official"


def test_event_with_requirement_ids_does_not_search(regulatory_db, monkeypatch):
    def fail_search(*args, **kwargs):
        raise AssertionError("semantic search must not run")

    monkeypatch.setattr("app.tenant.regulatory.service.search_legal_requirements", fail_search)
    trigger = load_regulation_trigger(regulatory_db, "evt_full")

    assert [item.id for item in resolve_requirements_for_trigger(regulatory_db, trigger)] == [1]


def test_missing_authoritative_requirement_is_rejected(regulatory_db):
    regulatory_db.add(RegulationEvent(
        event_id="evt_missing_requirement", event_type="regulation.change.ready",
        regulation_id=1, version_id=1, payload={"requirement_ids": [999]},
    ))
    regulatory_db.commit()

    trigger = load_regulation_trigger(regulatory_db, "evt_missing_requirement")
    with pytest.raises(InvalidRegulationTriggerError):
        resolve_requirements_for_trigger(regulatory_db, trigger)


def test_payload_missing_fields_are_backfilled_from_database(regulatory_db):
    regulatory_db.add(RegulationEvent(
        event_id="evt_sparse", event_type="regulation.change.ready",
        regulation_id=1, version_id=1, payload={},
    ))
    regulatory_db.commit()

    trigger = load_regulation_trigger(regulatory_db, "evt_sparse")

    assert trigger.regulation_id == 1 and trigger.version_id == 1
    assert trigger.change_ids == [1]
    assert trigger.requirement_ids == [1]
    assert trigger.legal_unit_ids == [1]


@pytest.mark.parametrize("field,bad_value", [("regulation_id", 2), ("version_id", 2)])
def test_payload_database_identity_conflict_is_rejected(regulatory_db, field, bad_value):
    regulatory_db.add(RegulationEvent(
        event_id=f"evt_bad_{field}", event_type="regulation.change.ready",
        regulation_id=1, version_id=1, payload={field: bad_value},
    ))
    regulatory_db.commit()

    with pytest.raises(TriggerDataConflictError):
        load_regulation_trigger(regulatory_db, f"evt_bad_{field}")


def test_unsupported_event_type_is_rejected(regulatory_db):
    regulatory_db.add(RegulationEvent(
        event_id="evt_other", event_type="regulation.source.ready",
        regulation_id=1, version_id=1, payload={},
    ))
    regulatory_db.commit()

    with pytest.raises(UnsupportedRegulationEventError):
        load_regulation_trigger(regulatory_db, "evt_other")


def test_legal_unit_resolution_precedes_search(regulatory_db, monkeypatch):
    change = regulatory_db.get(RegulationChange, 1)
    change.requirement_ids = []
    regulatory_db.add(RegulationEvent(
        event_id="evt_unit", event_type="regulation.change.ready", regulation_id=1,
        version_id=1, payload={"change_ids": [1], "affected_legal_unit_ids": [1]},
    ))
    regulatory_db.commit()

    def fail_search(*args, **kwargs):
        raise AssertionError("legal unit resolution must precede semantic search")

    monkeypatch.setattr("app.tenant.regulatory.service.search_legal_requirements", fail_search)
    trigger = load_regulation_trigger(regulatory_db, "evt_unit")

    assert [item.id for item in resolve_requirements_for_trigger(regulatory_db, trigger)] == [1]


def test_semantic_search_is_last_fallback(regulatory_db, monkeypatch):
    regulatory_db.add(RegulationEvent(
        event_id="evt_search", event_type="regulation.change.ready", regulation_id=1,
        version_id=1, payload={"topics": ["透明度"]},
    ))
    regulatory_db.query(RegulationChange).delete()
    regulatory_db.commit()
    requirement = regulatory_db.get(Requirement, 1)
    expected = RequirementOut.model_validate(requirement)
    calls = []

    def fake_search(db, query, *, regulation_ids, top_k=8):
        calls.append((query, regulation_ids))
        return [expected]

    monkeypatch.setattr("app.tenant.regulatory.service.search_legal_requirements", fake_search)
    trigger = load_regulation_trigger(regulatory_db, "evt_search")
    resolved = resolve_requirements_for_trigger(regulatory_db, trigger)

    assert [item.id for item in resolved] == [1]
    assert calls == [("透明度", [1])]
