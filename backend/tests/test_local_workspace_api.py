from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


def test_desktop_can_create_product_only_inside_an_existing_local_workspace(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNTIME_MODE", "local")
    monkeypatch.setenv("LOCAL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("RUNTIME_TOKEN", "bridge-only-test-token")
    monkeypatch.setenv("EVALUATION_AUTH_BYPASS", "true")
    get_settings.cache_clear()
    headers = {"X-Runtime-Token": "bridge-only-test-token"}
    try:
        with TestClient(app) as client:
            workspace = client.post("/api/companies", headers=headers, json={
                "name": "Private workspace",
                "industry": "",
                "country": "",
                "target_markets": [],
                "business_model": "offline",
            })
            assert workspace.status_code == 201, workspace.text
            company_id = workspace.json()["id"]

            product = client.post("/api/v1/evaluation/products", headers=headers, json={
                "company_id": company_id,
                "name": "Private product",
                "description": "Stored locally",
                "markets": ["EU"],
            })
            assert product.status_code == 201, product.text
            assert product.json()["company_id"] == company_id

            invalid = client.post("/api/v1/evaluation/products", headers=headers, json={
                "company_id": company_id + 999,
                "name": "Foreign product",
            })
            assert invalid.status_code == 400
    finally:
        get_settings.cache_clear()
