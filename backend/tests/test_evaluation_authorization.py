from fastapi.testclient import TestClient

from app.main import app
from app.core.config import get_settings
import pytest

ORIGIN = {"Origin": "http://localhost:5173"}

@pytest.fixture(autouse=True)
def enforce_auth(monkeypatch):
    monkeypatch.setenv("EVALUATION_AUTH_BYPASS", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _workspace(client: TestClient, name: str):
    start = client.post("/api/v1/evaluation/start", headers=ORIGIN, json={
        "name": name, "email": f"{name.lower()}@example.com",
        "company_name": f"{name} workspace", "edition": "developer",
    })
    assert start.status_code == 201, start.text
    product = client.post("/api/v1/evaluation/products", headers=ORIGIN, json={
        "name": f"{name} product", "description": "test", "markets": ["EU"],
    })
    assert product.status_code == 201, product.text
    return start.json()["company_id"], product.json()["id"], client.cookies.get("datashield_evaluation")


def test_anonymous_tenant_routes_are_rejected():
    with TestClient(app) as client:
        assert client.get("/api/v1/today", params={"tenant_id": 1, "product_id": 1}).status_code == 401
        assert client.get("/api/v1/findings", params={"tenant_id": 1}).status_code == 401
        assert client.get("/api/v1/ui/understanding/products/1/twin", params={"company_id": 1}).status_code == 401


def test_session_cannot_read_or_analyze_foreign_product():
    with TestClient(app) as client_a, TestClient(app) as client_b:
        company_a, product_a, token_a = _workspace(client_a, "Alice")
        company_b, product_b, _ = _workspace(client_b, "Bob")
        client_a.cookies.set("datashield_evaluation", token_a)
        assert client_a.get("/api/v1/today", params={"tenant_id": company_b, "product_id": product_b}).status_code == 404
        assert client_a.get(f"/api/v1/ui/understanding/products/{product_b}/twin", params={"company_id": company_b}).status_code == 404
        response = client_a.post("/api/v1/tenant-agent/analyze", headers=ORIGIN, json={
            "tenant_id": company_b, "product_id": product_b,
            "trigger_type": "MANUAL_SCAN", "requirement_ids": [],
        })
        assert response.status_code == 404
        assert company_a != company_b and product_a != product_b


def test_state_change_rejects_untrusted_origin():
    with TestClient(app) as client:
        company, product, _ = _workspace(client, "Origin")
        response = client.post("/api/v1/tenant-agent/analyze", headers={"Origin": "https://evil.example"}, json={
            "tenant_id": company, "product_id": product,
            "trigger_type": "MANUAL_SCAN", "requirement_ids": [],
        })
        assert response.status_code == 403
