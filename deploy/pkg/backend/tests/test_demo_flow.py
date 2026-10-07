"""Browser API demo path: every result is created by the real domain services."""
import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app

ORIGIN={"Origin":"http://localhost:5173"}

@pytest.fixture(autouse=True)
def enforce_auth(monkeypatch):
    monkeypatch.setenv("EVALUATION_AUTH_BYPASS","false"); get_settings.cache_clear(); yield; get_settings.cache_clear()

def test_complete_isolated_demo_flow():
    with TestClient(app) as client:
        created=client.post("/api/v1/evaluation/demo",headers=ORIGIN)
        assert created.status_code==201,created.text
        scope=created.json(); finding_id=scope["finding_ids"][0]
        detail=client.get(f"/api/v1/findings/{finding_id}",params={"tenant_id":scope["company_id"]})
        assert detail.status_code==200
        assert detail.json()["requirements"] and detail.json()["legal_evidence"]

        remediation=client.post(f"/api/v1/findings/{finding_id}/remediations",headers=ORIGIN,json={"tenant_id":scope["company_id"],"remediation_type":"DOCUMENT_CHANGE","document_type":"AI transparency notice"})
        assert remediation.status_code==201,remediation.text
        remediation_id=remediation.json()["remediation"]["id"]
        approved=client.post(f"/api/v1/remediations/{remediation_id}/approve",headers=ORIGIN,json={"tenant_id":scope["company_id"],"note":"Approved for implementation"})
        assert approved.status_code==200
        assert approved.json()["remediation"]["status"]=="APPROVED"

        feedback=client.post("/api/v1/feedback",headers=ORIGIN,json={"tenant_id":scope["company_id"],"product_id":scope["product_id"],"finding_id":finding_id,"feedback_type":"FACT_CORRECTION","raw_text":"We already disclose AI use to users.","created_by":"evaluation-user"})
        assert feedback.status_code==201,feedback.text
        candidate=feedback.json()["candidates"][0]
        assert candidate["status"]=="PROPOSED"
        confirmed=client.post(f"/api/v1/feedback-candidates/{candidate['id']}/confirm",headers=ORIGIN,json={"tenant_id":scope["company_id"]})
        assert confirmed.status_code==200 and confirmed.json()["status"]=="CONFIRMED"
        applied=client.post(f"/api/v1/feedback-candidates/{candidate['id']}/apply",headers=ORIGIN,json={"tenant_id":scope["company_id"]})
        assert applied.status_code==200,applied.text
        assert applied.json()["status"]=="APPLIED"
        assert applied.json()["applied_twin_version_id"] and applied.json()["reanalysis_run_id"]

        today=client.get("/api/v1/today",params={"tenant_id":scope["company_id"],"product_id":scope["product_id"]})
        assert today.status_code==200
        assert today.json()["needs_review"]==[]
        assert today.json()["waiting_for_you"]==[]
