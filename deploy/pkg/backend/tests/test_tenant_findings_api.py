"""Tenant boundaries and query contracts for Finding APIs."""

from fastapi.testclient import TestClient

from app.main import app

from test_tenant_agent import _analyze, _scenario


def test_findings_list_and_detail_are_tenant_scoped():
    with TestClient(app) as client:
        first = _scenario()
        second = _scenario()
        first_id = _analyze(client, first).json()["finding_ids"][0]
        second_id = _analyze(client, second).json()["finding_ids"][0]

        listing = client.get("/api/v1/findings", params={"tenant_id": first["tenant_id"]})
        assert listing.status_code == 200
        ids = {item["id"] for item in listing.json()}
        assert first_id in ids and second_id not in ids
        assert listing.json()[0]["requirement_count"] >= 1
        assert listing.json()[0]["evidence_count"] >= 1

        assert client.get(
            f"/api/v1/findings/{second_id}", params={"tenant_id": first["tenant_id"]}
        ).status_code == 404
        assert client.get(
            f"/api/v1/findings/{first_id}", params={"tenant_id": first["tenant_id"]}
        ).status_code == 200


def test_findings_list_requires_tenant_and_filters_product_status():
    with TestClient(app) as client:
        scenario = _scenario()
        finding_id = _analyze(client, scenario).json()["finding_ids"][0]
        assert client.get("/api/v1/findings").status_code == 422
        listing = client.get("/api/v1/findings", params={
            "tenant_id": scenario["tenant_id"], "product_id": scenario["product_id"],
            "status": "OPEN",
        })
        assert [item["id"] for item in listing.json()] == [finding_id]
        empty = client.get("/api/v1/findings", params={
            "tenant_id": scenario["tenant_id"], "status": "RESOLVED",
        })
        assert empty.json() == []
