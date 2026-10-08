from app.api.feedback import router
def test_feedback_routes_are_registered():
    paths={route.path for route in router.routes if hasattr(route,"path")}
    assert "/v1/feedback" in paths
    assert "/v1/feedback-candidates/{candidate_id}/apply" in paths
    assert "/v1/products/{product_id}/feedback" in paths


def test_fact_correction_without_finding_accepted():
    """FACT_CORRECTION 允许不绑定 finding/remediation（产品画像页直接纠正）。"""
    import uuid as _uuid

    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        reg = client.post(
            "/api/v1/auth/register",
            headers={"Origin": "http://localhost:5173"},
            json={
                "email": f"fb-{ _uuid.uuid4().hex[:8]}@example.com",
                "password": "Sup3rSecret!",
                "name": "FB User",
                "company_name": "FB Co",
                "edition": "developer",
            },
        )
        assert reg.status_code == 201, reg.text
        body = reg.json()
        product = client.post(
            "/api/v1/evaluation/products",
            headers={"Origin": "http://localhost:5173"},
            json={"name": "P", "description": "d", "markets": [], "category": ""},
        )
        assert product.status_code == 201, product.text
        resp = client.post(
            "/api/v1/feedback",
            headers={"Origin": "http://localhost:5173"},
            json={
                "tenant_id": body["company_id"],
                "product_id": product.json()["id"],
                "feedback_type": "FACT_CORRECTION",
                "raw_text": "我们已经有 AI 披露了",
                "created_by": "test",
            },
        )
        assert resp.status_code == 201, resp.text
