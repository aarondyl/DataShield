"""Tenant-scoped Remediation API integration tests using the deterministic model."""

import pytest
from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models import Finding
from app.tenant.remediation.planner import RemediationProviderError

from test_tenant_agent import _analyze, _scenario


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as value:
        yield value


def _finding(client, **scenario_options):
    scenario = _scenario(**scenario_options)
    response = _analyze(client, scenario)
    assert response.status_code == 201, response.text
    scenario["finding_id"] = response.json()["finding_ids"][0]
    return scenario


def _request(scenario, remediation_type="CODE_CHANGE"):
    body = {"tenant_id": scenario["tenant_id"], "remediation_type": remediation_type}
    if remediation_type == "DOCUMENT_CHANGE":
        body["document_type"] = "AI transparency notice"
    return body


def _create(client, scenario, remediation_type="CODE_CHANGE"):
    return client.post(
        f"/api/v1/findings/{scenario['finding_id']}/remediations",
        json=_request(scenario, remediation_type),
    )


def test_create_code_change_returns_typed_canonical_detail(client):
    scenario = _finding(client)
    response = _create(client, scenario)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["remediation"]["remediation_type"] == "CODE_CHANGE"
    assert body["remediation"]["plan"]["coding_prompt"].startswith("# Context")
    assert body["requirements"][0]["id"] == scenario["requirement_id"]
    assert body["legal_evidence"][0]["legal_unit_id"] == scenario["legal_unit_id"]
    assert body["product_twin_version"]["id"] == scenario["twin_id"]
    assert body["remediation"]["model_provider"] == "mock"
    assert body["remediation"]["prompt_version"] == "remediation-code-v1"


def test_create_document_change_is_draft_and_writes_no_file(client, tmp_path):
    scenario = _finding(client)
    before = set(tmp_path.iterdir())
    response = _create(client, scenario, "DOCUMENT_CHANGE")
    assert response.status_code == 201, response.text
    plan = response.json()["remediation"]["plan"]
    assert plan["document_type"] == "AI transparency notice"
    assert plan["draft_status"] == "DRAFT_REQUIRES_HUMAN_REVIEW"
    assert set(tmp_path.iterdir()) == before


def test_list_and_detail_are_deterministic_and_typed(client):
    scenario = _finding(client)
    first = _create(client, scenario).json()
    second = _create(client, scenario, "DOCUMENT_CHANGE").json()
    listing = client.get(
        f"/api/v1/findings/{scenario['finding_id']}/remediations",
        params={"tenant_id": scenario["tenant_id"]},
    )
    assert listing.status_code == 200
    assert [item["id"] for item in listing.json()] == [
        second["remediation"]["id"], first["remediation"]["id"]
    ]
    detail = client.get(
        f"/api/v1/remediations/{first['remediation']['id']}",
        params={"tenant_id": scenario["tenant_id"]},
    )
    assert detail.status_code == 200
    assert detail.json()["remediation"]["plan"]["requested_changes"]


@pytest.mark.parametrize("decision,expected", [("approve", "APPROVED"), ("reject", "REJECTED")])
def test_decisions_are_idempotent_and_do_not_change_finding(client, decision, expected):
    scenario = _finding(client)
    remediation_id = _create(client, scenario).json()["remediation"]["id"]
    url = f"/api/v1/remediations/{remediation_id}/{decision}"
    request = {"tenant_id": scenario["tenant_id"], "note": "reviewed"}
    first = client.post(url, json=request)
    second = client.post(url, json=request)
    assert first.status_code == second.status_code == 200
    assert second.json()["remediation"]["status"] == expected
    with SessionLocal() as db:
        assert db.get(Finding, scenario["finding_id"]).status == "OPEN"


@pytest.mark.parametrize(
    "first,second", [("approve", "reject"), ("reject", "approve")]
)
def test_opposite_terminal_decision_conflicts(client, first, second):
    scenario = _finding(client)
    remediation_id = _create(client, scenario).json()["remediation"]["id"]
    payload = {"tenant_id": scenario["tenant_id"]}
    assert client.post(f"/api/v1/remediations/{remediation_id}/{first}", json=payload).status_code == 200
    assert client.post(f"/api/v1/remediations/{remediation_id}/{second}", json=payload).status_code == 409


def test_not_found_and_required_tenant_contracts(client):
    scenario = _finding(client)
    assert client.post("/api/v1/findings/999999/remediations", json=_request(scenario)).status_code == 404
    assert client.get("/api/v1/remediations/999999", params={"tenant_id": scenario["tenant_id"]}).status_code == 404
    assert client.get(f"/api/v1/findings/{scenario['finding_id']}/remediations").status_code == 422
    assert client.get("/api/v1/remediations/1").status_code == 422


def test_every_operation_hides_cross_tenant_resources(client):
    owner = _finding(client)
    other = _scenario()
    remediation_id = _create(client, owner).json()["remediation"]["id"]
    assert client.post(
        f"/api/v1/findings/{owner['finding_id']}/remediations", json=_request(other)
    ).status_code == 404
    assert client.get(
        f"/api/v1/findings/{owner['finding_id']}/remediations",
        params={"tenant_id": other["tenant_id"]},
    ).status_code == 404
    assert client.get(
        f"/api/v1/remediations/{remediation_id}", params={"tenant_id": other["tenant_id"]}
    ).status_code == 404
    for decision in ("approve", "reject"):
        assert client.post(
            f"/api/v1/remediations/{remediation_id}/{decision}",
            json={"tenant_id": other["tenant_id"]},
        ).status_code == 404


@pytest.mark.parametrize("finding_status", ["DISMISSED", "RESOLVED"])
def test_only_open_finding_can_create_remediation(client, finding_status):
    scenario = _finding(client)
    with SessionLocal() as db:
        finding = db.get(Finding, scenario["finding_id"])
        finding.status = finding_status
        db.commit()
    assert _create(client, scenario).status_code == 409


def test_invalid_request_is_422(client):
    scenario = _finding(client)
    response = client.post(
        f"/api/v1/findings/{scenario['finding_id']}/remediations",
        json={"tenant_id": scenario["tenant_id"], "remediation_type": "DOCUMENT_CHANGE"},
    )
    assert response.status_code == 422


def test_provider_failure_is_502_and_saves_nothing(client, monkeypatch):
    scenario = _finding(client)
    class FailingClient:
        provider_name = "test"
        model_name = "failure"
        def chat_json(self, *args, **kwargs):
            raise TimeoutError("provider timeout")
    monkeypatch.setattr("app.tenant.remediation.planner.get_llm_client", lambda: FailingClient())
    response = _create(client, scenario)
    assert response.status_code == 502
    listing = client.get(
        f"/api/v1/findings/{scenario['finding_id']}/remediations",
        params={"tenant_id": scenario["tenant_id"]},
    )
    assert listing.json() == []


def test_invalid_model_payload_is_422_and_saves_nothing(client, monkeypatch):
    scenario = _finding(client)
    class InvalidClient:
        provider_name = "test"
        model_name = "invalid"
        def chat_json(self, *args, **kwargs):
            return "not-json"
    monkeypatch.setattr("app.tenant.remediation.planner.get_llm_client", lambda: InvalidClient())
    assert _create(client, scenario).status_code == 422


def test_grounding_invalid_model_reference_is_422(client, monkeypatch):
    scenario = _finding(client)
    class UngroundedClient:
        provider_name = "test"
        model_name = "ungrounded"
        def chat_json(self, *args, **kwargs):
            return {
                "document_type": "AI transparency notice",
                "proposed_changes": [{"section": "Disclosure", "change": "Draft text", "rationale": "Finding"}],
                "draft_text": "DRAFT — REQUIRES HUMAN REVIEW. [TO CONFIRM: product facts]",
                "evidence": [{
                    "requirement_id": 999999, "legal_unit_id": 999999,
                    "regulation_id": 1, "regulation_name": "Invented", "version_id": 1,
                    "version": 1, "article": "1", "heading": "", "source_url": "",
                }],
                "acceptance_criteria": ["Human review"],
            }
    monkeypatch.setattr("app.tenant.remediation.planner.get_llm_client", lambda: UngroundedClient())
    assert _create(client, scenario, "DOCUMENT_CHANGE").status_code == 422


def test_approve_is_review_only_and_exposes_no_execution_route(client, tmp_path):
    scenario = _finding(client)
    marker = tmp_path / "unchanged.txt"
    marker.write_text("unchanged")
    remediation_id = _create(client, scenario).json()["remediation"]["id"]
    assert client.post(
        f"/api/v1/remediations/{remediation_id}/approve",
        json={"tenant_id": scenario["tenant_id"]},
    ).status_code == 200
    assert marker.read_text() == "unchanged"
    assert client.post(
        f"/api/v1/remediations/{remediation_id}/execute",
        json={"tenant_id": scenario["tenant_id"]},
    ).status_code == 404
