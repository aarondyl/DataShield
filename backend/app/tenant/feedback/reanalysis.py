"""Retry-safe, requirement-scoped feedback reanalysis."""
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.tenant.agent.graph import get_tenant_graph
from app.tenant.feedback.schemas import CandidateStatus
from app.tenant.feedback.service import FeedbackConflictError, owned_candidate, requirement_ids
from app.tenant.findings.schemas import TenantAgentRunStatus, TenantTriggerType
from app.tenant.findings.service import create_pending_agent_run, mark_run_failed

def reanalyze_confirmed_candidate(db:Session,tenant_id:int,candidate_id:int):
    candidate=owned_candidate(db,tenant_id,candidate_id)
    if candidate.status!=CandidateStatus.CONFIRMED.value or not candidate.applied_twin_version_id: raise FeedbackConflictError("Candidate correction has not been written to Product Twin")
    frozen=requirement_ids(db,candidate.id)
    if not frozen: raise FeedbackConflictError("Candidate has no frozen Requirement scope")
    run=create_pending_agent_run(db,tenant_id=tenant_id,product_id=candidate.product_id,trigger_type=TenantTriggerType.FEEDBACK_REANALYSIS,trigger_id=str(candidate.id),prompt_version="tenant-applicability-v1")
    candidate.reanalysis_run_id=run.id; candidate.last_error=""; db.commit()
    initial={"tenant_id":tenant_id,"product_id":candidate.product_id,"trigger_type":"FEEDBACK_REANALYSIS","trigger_id":str(candidate.id),"requirement_ids":frozen,"feedback_twin_version_id":candidate.applied_twin_version_id,"run_id":run.id,"requirements":[],"ready_requirement_ids":[],"legal_evidence":[],"missing_context":[],"applicability_results":[],"gap_results":[],"finding_candidates":[],"finding_ids":[],"status":"PENDING","errors":[]}
    try:
        result=get_tenant_graph().invoke(initial)
    except Exception as exc:
        with SessionLocal() as inner: mark_run_failed(inner,run.id,str(exc))
        candidate=owned_candidate(db,tenant_id,candidate_id); candidate.last_error=str(exc)[:4000]; db.commit(); return candidate
    candidate=owned_candidate(db,tenant_id,candidate_id)
    if result.get("status")==TenantAgentRunStatus.COMPLETED.value: candidate.status=CandidateStatus.APPLIED.value; candidate.last_error=""
    else: candidate.last_error=f"Reanalysis ended with {result.get('status')}"
    db.commit(); db.refresh(candidate); return candidate
