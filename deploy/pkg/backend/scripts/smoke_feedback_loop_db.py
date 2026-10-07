"""Small database smoke for feedback persistence on SQLite/PostgreSQL."""
from pathlib import Path
import sys
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

BACKEND_DIR=Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0,str(BACKEND_DIR))
from app.db.session import engine
from app.models import Finding, FindingRequirement
from app.tenant.feedback.schemas import FactCorrectionProposal, FeedbackCreateRequest
from app.tenant.feedback.service import create_feedback, requirement_ids

required={"feedback","feedback_candidates","feedback_candidate_requirements"}
present=set(inspect(engine).get_table_names())
assert required <= present, f"missing feedback tables: {sorted(required-present)}"
with Session(engine) as db:
    finding=db.scalar(select(Finding).order_by(Finding.id.desc()).limit(1))
    assert finding is not None, "Tenant Intelligence smoke must create a Finding first"
    expected=list(db.scalars(select(FindingRequirement.requirement_id).where(FindingRequirement.finding_id==finding.id).order_by(FindingRequirement.requirement_id)).all())
    feedback,candidate=create_feedback(db,FeedbackCreateRequest(tenant_id=finding.tenant_id,product_id=finding.product_id,finding_id=finding.id,feedback_type="FACT_CORRECTION",raw_text="We already support this capability.",created_by="postgres-smoke"),FactCorrectionProposal(proposed_name="account_deletion",proposed_status="PRESENT",confidence=0.9,reasoning_summary="User reported an existing capability."),model_provider="mock",model_name="deterministic",prompt_version="feedback-candidate-v1")
    assert feedback.raw_text == "We already support this capability."
    assert candidate.status == "PROPOSED"
    assert requirement_ids(db,candidate.id) == expected
print("Feedback Loop persistence smoke passed")
