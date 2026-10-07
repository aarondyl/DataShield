"""Tenant Intelligence graph behavior and full event-to-finding integration."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import SessionLocal
from app.main import app
from app.models import (
    Company,
    Finding,
    Product,
    ProductTwinFact,
    ProductTwinVersion,
    Regulation,
    RegulationChange,
    RegulationEvent,
    RegulationVersion,
    Requirement,
    LegalUnit,
    TenantAgentRun,
    TenantMissingContextItem,
)
from app.tenant.agent.nodes.applicability import analyze_applicability
from app.tenant.context.schemas import ProductContext
from app.tenant.regulatory.schemas import RequirementContext


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as value:
        yield value


def _fact(version_id, group, name, status="PRESENT", *, source="USER", confirmed=True, confidence=.9):
    return ProductTwinFact(
        version_id=version_id,
        group_name=group,
        name=name,
        status=status,
        confidence=confidence,
        source_kind=source,
        evidence=[{"type": "USER_DESCRIPTION", "reason": "test evidence"}],
        scan_scope={"complete": confirmed},
        confirmation_status="CONFIRMED" if confirmed else "UNREVIEWED",
    )


def _scenario(*, market="EU", control_status="NOT_DETECTED", include_subject=True,
              include_ai=True, confirmed_absence=False, legacy=False):
    suffix = uuid.uuid4().hex[:10]
    with SessionLocal() as db:
        company = Company(name=f"Tenant {suffix}", target_markets=[market])
        db.add(company)
        db.flush()
        product = Product(
            company_id=company.id,
            name=f"Product {suffix}",
            target_markets=[market],
        )
        db.add(product)
        db.flush()
        twin = None
        if not legacy:
            twin = ProductTwinVersion(product_id=product.id, version_number=1, reason="test")
            db.add(twin)
            db.flush()
            facts = [_fact(twin.id, "market_clues", market)]
            if include_subject:
                facts.append(_fact(twin.id, "subject_types", "provider"))
            if include_ai:
                facts.append(_fact(twin.id, "features", "ai_features"))
            if confirmed_absence:
                facts.append(_fact(twin.id, "controls", "ai_disclosure_absent"))
            else:
                facts.append(_fact(
                    twin.id, "controls", "ai_disclosure", control_status,
                    source="REPOSITORY", confirmed=False, confidence=.8,
                ))
            db.add_all(facts)

        regulation = Regulation(
            name=f"EU AI Test Act {suffix}", jurisdiction="EU",
            canonical_source_url=f"https://example.eu/{suffix}",
        )
        db.add(regulation)
        db.flush()
        version = RegulationVersion(
            regulation_id=regulation.id,
            version_number=1,
            normalized_text="Article 50 AI transparency",
            content_hash=(suffix * 7)[:64].ljust(64, "a"),
            is_current=True,
        )
        db.add(version)
        db.flush()
        regulation.current_version_id = version.id
        unit = LegalUnit(
            version_id=version.id, unit_type="article", unit_number="Article 50",
            heading="Transparency", text="Providers shall disclose interaction with an AI system.",
        )
        db.add(unit)
        db.flush()
        requirement = Requirement(
            regulation_id=regulation.id, version_id=version.id, legal_unit_id=unit.id,
            requirement_type="obligation", subject_type="provider", action_type="inform",
            object_type="AI system", conditions_json=[], exceptions_json=[],
            summary="Provide AI transparency disclosure", confidence=.9, status="ACTIVE",
        )
        db.add(requirement)
        db.flush()
        change = RegulationChange(
            regulation_id=regulation.id, to_version_id=version.id, legal_unit_id=unit.id,
            change_type="ADDED", new_text=unit.text, semantic_summary="AI transparency",
            materiality="HIGH", requirement_ids=[requirement.id],
        )
        db.add(change)
        db.flush()
        event_id = f"evt_{suffix}"
        db.add(RegulationEvent(
            event_id=event_id, event_type="regulation.change.ready",
            regulation_id=regulation.id, version_id=version.id,
            payload={"change_ids": [change.id], "requirement_ids": [requirement.id]},
        ))
        db.commit()
        return {
            "tenant_id": company.id, "product_id": product.id, "twin_id": twin.id if twin else None,
            "regulation_id": regulation.id, "requirement_id": requirement.id,
            "legal_unit_id": unit.id, "event_id": event_id,
        }


def _analyze(client, scenario, **overrides):
    body = {
        "tenant_id": scenario["tenant_id"],
        "product_id": scenario["product_id"],
        "trigger_type": "REGULATION_CHANGE",
        "trigger_id": scenario["event_id"],
    }
    body.update(overrides)
    return client.post("/api/v1/tenant-agent/analyze", json=body)


def test_regulation_change_full_flow_to_canonical_finding(client):
    scenario = _scenario()
    response = _analyze(client, scenario)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert len(body["finding_ids"]) == 1

    detail = client.get(
        f"/api/v1/findings/{body['finding_ids'][0]}",
        params={"tenant_id": scenario["tenant_id"]},
    )
    assert detail.status_code == 200, detail.text
    payload = detail.json()
    assert payload["finding"]["product_twin_version_id"] == scenario["twin_id"]
    assert payload["requirements"][0]["id"] == scenario["requirement_id"]
    assert payload["legal_evidence"][0]["legal_unit_id"] == scenario["legal_unit_id"]
    assert payload["applicability"][0]["applies"] is True
    assert payload["gap"][0]["gap_status"] == "POTENTIAL"


def test_manual_scan_explicit_requirement_ids(client):
    scenario = _scenario()
    response = client.post("/api/v1/tenant-agent/analyze", json={
        "tenant_id": scenario["tenant_id"], "product_id": scenario["product_id"],
        "trigger_type": "MANUAL_SCAN", "requirement_ids": [scenario["requirement_id"]],
    })
    assert response.status_code == 201, response.text
    assert response.json()["finding_ids"]
    with SessionLocal() as db:
        run = db.get(TenantAgentRun, response.json()["run_id"])
        assert run.trigger_id is None
        assert "event_id" not in run.input_snapshot_json["trigger"]


def test_non_applicable_jurisdiction_creates_no_finding(client):
    scenario = _scenario(market="US")
    response = _analyze(client, scenario)
    assert response.status_code == 201
    assert response.json()["status"] == "COMPLETED"
    assert response.json()["finding_ids"] == []


def test_present_control_is_no_gap_and_creates_no_finding(client):
    scenario = _scenario(control_status="PRESENT")
    response = _analyze(client, scenario)
    assert response.status_code == 201
    assert response.json()["finding_ids"] == []
    with SessionLocal() as db:
        run = db.get(TenantAgentRun, response.json()["run_id"])
        assert run.output_json["gap_results"][0]["gap_status"] == "NO_GAP"


def test_confirmed_absence_creates_confirmed_finding(client):
    scenario = _scenario(confirmed_absence=True)
    response = _analyze(client, scenario)
    assert response.status_code == 201, response.text
    with SessionLocal() as db:
        finding = db.get(Finding, response.json()["finding_ids"][0])
        assert finding.gap_status == "CONFIRMED"


def test_missing_context_marks_run_and_persists_question(client):
    scenario = _scenario(include_subject=False, include_ai=False)
    response = _analyze(client, scenario)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "NEEDS_USER_INPUT"
    assert body["finding_ids"] == []
    with SessionLocal() as db:
        rows = db.scalars(select(TenantMissingContextItem).where(
            TenantMissingContextItem.run_id == body["run_id"]
        )).all()
        assert {item.field_path for item in rows} >= {"subject_types", "ai_features"}


def test_legacy_product_fallback_reaches_needs_user_input(client):
    scenario = _scenario(legacy=True)
    response = _analyze(client, scenario)
    assert response.status_code == 201
    assert response.json()["status"] == "NEEDS_USER_INPUT"
    with SessionLocal() as db:
        run = db.get(TenantAgentRun, response.json()["run_id"])
        assert run.input_snapshot_json["product_context"]["used_legacy_fallback"] is True
        assert run.input_snapshot_json["product_twin_version_id"] is None


def test_mixed_requirements_keep_finding_and_missing_context(client):
    scenario = _scenario()
    with SessionLocal() as db:
        first = db.get(Requirement, scenario["requirement_id"])
        second = Requirement(
            regulation_id=first.regulation_id, version_id=first.version_id,
            legal_unit_id=first.legal_unit_id, requirement_type="obligation",
            subject_type="provider", action_type="protect", object_type="biometric data",
            conditions_json=[], exceptions_json=[], summary="Protect biometric data",
            confidence=.9, status="ACTIVE",
        )
        db.add(second)
        db.commit()
        second_id = second.id
    response = client.post("/api/v1/tenant-agent/analyze", json={
        "tenant_id": scenario["tenant_id"], "product_id": scenario["product_id"],
        "trigger_type": "MANUAL_SCAN",
        "requirement_ids": [scenario["requirement_id"], second_id],
    })
    body = response.json()
    assert response.status_code == 201, response.text
    assert body["status"] == "NEEDS_USER_INPUT"
    assert body["finding_ids"]
    assert any(item["field_path"] == "data_types.biometric" for item in body["missing_context"])


def test_empty_manual_scan_completes_without_llm_or_finding(client):
    scenario = _scenario()
    response = client.post("/api/v1/tenant-agent/analyze", json={
        "tenant_id": scenario["tenant_id"], "product_id": scenario["product_id"],
        "trigger_type": "MANUAL_SCAN",
    })
    assert response.status_code == 201
    assert response.json() == {
        "run_id": response.json()["run_id"], "status": "COMPLETED",
        "finding_ids": [], "missing_context": [],
    }


def test_invalid_llm_output_fails_safe(monkeypatch):
    class InvalidClient:
        def chat_json(self, *args, **kwargs):
            return {"applies": True}

    monkeypatch.setattr("app.tenant.agent.nodes.applicability.get_llm_client", lambda: InvalidClient())
    requirement = RequirementContext(
        id=99, regulation_id=1, version_id=1, requirement_type="obligation",
        subject_type="", action_type="assess", object_type="service", summary="Assess service",
        confidence=.9, status="ACTIVE",
    )
    result = analyze_applicability({
        "product_context": ProductContext(tenant_id=1, product_id=1),
        "requirements": [requirement], "ready_requirement_ids": [99],
        "legal_evidence": [], "applicability_results": [], "missing_context": [],
    })
    assert result["applicability_results"][0].applies is None
    assert result["applicability_results"][0].confidence == 0


def test_llm_error_fails_safe(monkeypatch):
    class FailingClient:
        def chat_json(self, *args, **kwargs):
            raise RuntimeError("provider timeout")

    monkeypatch.setattr("app.tenant.agent.nodes.applicability.get_llm_client", lambda: FailingClient())
    requirement = RequirementContext(
        id=100, regulation_id=1, version_id=1, requirement_type="obligation",
        subject_type="", action_type="assess", object_type="service", summary="Assess service",
        confidence=.9, status="ACTIVE",
    )
    result = analyze_applicability({
        "product_context": ProductContext(tenant_id=1, product_id=1),
        "requirements": [requirement], "ready_requirement_ids": [100],
        "legal_evidence": [], "applicability_results": [], "missing_context": [],
    })
    assert result["applicability_results"][0].applies is None
    assert result["missing_context"][0].field_path == "applicability_review"


def test_needs_review_requirement_confidence_is_capped(client):
    scenario = _scenario()
    with SessionLocal() as db:
        db.get(Requirement, scenario["requirement_id"]).status = "NEEDS_REVIEW"
        db.commit()
    response = _analyze(client, scenario)
    with SessionLocal() as db:
        finding = db.get(Finding, response.json()["finding_ids"][0])
        assert finding.confidence <= .69


def test_product_twin_conflict_confidence_is_capped(client):
    scenario = _scenario()
    with SessionLocal() as db:
        db.add(_fact(
            scenario["twin_id"], "features", "ai_features", "NOT_DETECTED",
            source="REPOSITORY", confirmed=False,
        ))
        db.commit()
    response = _analyze(client, scenario)
    with SessionLocal() as db:
        finding = db.get(Finding, response.json()["finding_ids"][0])
        assert finding.confidence <= .69


def test_missing_and_invalid_events_map_to_http_errors(client):
    scenario = _scenario()
    missing = client.post("/api/v1/tenant-agent/analyze", json={
        "tenant_id": scenario["tenant_id"], "product_id": scenario["product_id"],
        "trigger_type": "REGULATION_CHANGE", "trigger_id": "evt_missing",
    })
    assert missing.status_code == 404
    with SessionLocal() as db:
        db.add(RegulationEvent(event_id=f"evt_bad_{uuid.uuid4().hex[:8]}", event_type="other.event"))
        db.commit()
        event_id = db.scalar(select(RegulationEvent.event_id).where(RegulationEvent.event_type == "other.event"))
    invalid = client.post("/api/v1/tenant-agent/analyze", json={
        "tenant_id": scenario["tenant_id"], "product_id": scenario["product_id"],
        "trigger_type": "REGULATION_CHANGE", "trigger_id": event_id,
    })
    assert invalid.status_code == 422


def test_ownership_mismatch_is_hidden_as_not_found(client):
    first = _scenario()
    second = _scenario()
    response = client.post("/api/v1/tenant-agent/analyze", json={
        "tenant_id": first["tenant_id"], "product_id": second["product_id"],
        "trigger_type": "MANUAL_SCAN", "requirement_ids": [first["requirement_id"]],
    })
    assert response.status_code == 404
