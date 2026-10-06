"""Tenant-scoped immutable feedback persistence."""
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import Feedback, FeedbackCandidate, FeedbackCandidateRequirement, Finding, FindingRequirement, Remediation, ProductTwinFact, ProductTwinVersion
from app.tenant.context.ownership import resolve_tenant_product
from app.tenant.feedback.schemas import CandidateRecord, CandidateStatus, FactCorrectionProposal, FeedbackCreateRequest

class FeedbackNotFoundError(RuntimeError): pass
class FeedbackConflictError(RuntimeError): pass
class FeedbackGroundingError(ValueError): pass

def _requirements(db, finding_id):
    return list(db.scalars(select(FindingRequirement.requirement_id).where(FindingRequirement.finding_id==finding_id).order_by(FindingRequirement.requirement_id)).all())

def _target(db, request):
    resolve_tenant_product(db, request.tenant_id, request.product_id)
    finding = db.get(Finding, request.finding_id) if request.finding_id else None
    remediation = db.get(Remediation, request.remediation_id) if request.remediation_id else None
    if remediation:
        if remediation.tenant_id != request.tenant_id or remediation.product_id != request.product_id: raise FeedbackNotFoundError("Target does not exist for this tenant")
        linked = db.get(Finding, remediation.finding_id)
        if finding and finding.id != linked.id: raise FeedbackGroundingError("Finding and Remediation targets conflict")
        finding = linked
    if request.finding_id and (not finding or finding.tenant_id != request.tenant_id or finding.product_id != request.product_id): raise FeedbackNotFoundError("Target does not exist for this tenant")
    return finding

def create_feedback(db: Session, request: FeedbackCreateRequest, proposal: FactCorrectionProposal | None=None, *, model_provider="", model_name="", prompt_version=""):
    finding=_target(db,request); row=Feedback(tenant_id=request.tenant_id,product_id=request.product_id,finding_id=finding.id if finding else None,remediation_id=request.remediation_id,feedback_type=request.feedback_type.value,raw_text=request.raw_text,created_by=request.created_by,useful=request.useful,negative_reason=request.negative_reason.value if request.negative_reason else None)
    try:
        db.add(row); db.flush(); candidate=None
        if proposal:
            if proposal.target_fact_id:
                fact=db.get(ProductTwinFact,proposal.target_fact_id); version=db.get(ProductTwinVersion,fact.version_id) if fact else None
                if not fact or not version or version.product_id != request.product_id: raise FeedbackGroundingError("Target fact is outside this product")
            candidate=FeedbackCandidate(feedback_id=row.id,tenant_id=request.tenant_id,product_id=request.product_id,candidate_type=proposal.candidate_type.value,status=(CandidateStatus.NEEDS_CLARIFICATION if proposal.needs_clarification else CandidateStatus.PROPOSED).value,target_fact_id=proposal.target_fact_id,proposed_name=proposal.proposed_name,proposed_value=proposal.proposed_value,proposed_status=proposal.proposed_status.value if proposal.proposed_status else None,reasoning_summary=proposal.reasoning_summary,confidence=proposal.confidence,clarification_question=proposal.clarification_question,model_provider=model_provider,model_name=model_name,prompt_version=prompt_version)
            db.add(candidate); db.flush()
            for rid in _requirements(db,finding.id if finding else 0): db.add(FeedbackCandidateRequirement(candidate_id=candidate.id,requirement_id=rid))
        db.commit(); db.refresh(row)
        return row,candidate
    except Exception: db.rollback(); raise

def attach_candidate(db: Session, feedback: Feedback, proposal: FactCorrectionProposal, *, model_provider="", model_name="", prompt_version=""):
    request = FeedbackCreateRequest(tenant_id=feedback.tenant_id, product_id=feedback.product_id,
        finding_id=feedback.finding_id, remediation_id=feedback.remediation_id,
        feedback_type=feedback.feedback_type, raw_text=feedback.raw_text, created_by=feedback.created_by,
        useful=feedback.useful, negative_reason=feedback.negative_reason)
    finding = _target(db, request)
    if proposal.target_fact_id:
        fact=db.get(ProductTwinFact,proposal.target_fact_id); version=db.get(ProductTwinVersion,fact.version_id) if fact else None
        if not fact or not version or version.product_id != feedback.product_id: raise FeedbackGroundingError("Target fact is outside this product")
    candidate=FeedbackCandidate(feedback_id=feedback.id,tenant_id=feedback.tenant_id,product_id=feedback.product_id,candidate_type=proposal.candidate_type.value,status=(CandidateStatus.NEEDS_CLARIFICATION if proposal.needs_clarification else CandidateStatus.PROPOSED).value,target_fact_id=proposal.target_fact_id,proposed_name=proposal.proposed_name,proposed_value=proposal.proposed_value,proposed_status=proposal.proposed_status.value if proposal.proposed_status else None,reasoning_summary=proposal.reasoning_summary,confidence=proposal.confidence,clarification_question=proposal.clarification_question,model_provider=model_provider,model_name=model_name,prompt_version=prompt_version)
    try:
        db.add(candidate); db.flush()
        for rid in _requirements(db,finding.id if finding else 0): db.add(FeedbackCandidateRequirement(candidate_id=candidate.id,requirement_id=rid))
        db.commit(); db.refresh(candidate); return candidate
    except Exception: db.rollback(); raise

def owned_candidate(db,tenant_id,candidate_id):
    row=db.scalar(select(FeedbackCandidate).where(FeedbackCandidate.id==candidate_id,FeedbackCandidate.tenant_id==tenant_id))
    if not row: raise FeedbackNotFoundError("Candidate does not exist for this tenant")
    resolve_tenant_product(db,tenant_id,row.product_id); return row

def requirement_ids(db,candidate_id):
    return list(db.scalars(select(FeedbackCandidateRequirement.requirement_id).where(FeedbackCandidateRequirement.candidate_id==candidate_id).order_by(FeedbackCandidateRequirement.requirement_id)).all())

def candidate_record(db,row):
    return CandidateRecord(id=row.id,feedback_id=row.feedback_id,tenant_id=row.tenant_id,product_id=row.product_id,candidate_type=row.candidate_type,status=row.status,target_fact_id=row.target_fact_id,proposed_name=row.proposed_name,proposed_value=row.proposed_value,proposed_status=row.proposed_status,reasoning_summary=row.reasoning_summary,confidence=row.confidence,clarification_question=row.clarification_question,clarification_answer=row.clarification_answer,applied_fact_id=row.applied_fact_id,applied_twin_version_id=row.applied_twin_version_id,reanalysis_run_id=row.reanalysis_run_id,last_error=row.last_error,requirement_ids=requirement_ids(db,row.id),created_at=row.created_at,updated_at=row.updated_at)

def get_feedback(db: Session, tenant_id: int, feedback_id: int):
    row = db.scalar(select(Feedback).where(Feedback.id == feedback_id, Feedback.tenant_id == tenant_id))
    if not row:
        raise FeedbackNotFoundError("Feedback does not exist for this tenant")
    resolve_tenant_product(db, tenant_id, row.product_id)
    return row

def list_feedback(db: Session, tenant_id: int, product_id: int):
    resolve_tenant_product(db, tenant_id, product_id)
    return list(db.scalars(select(Feedback).where(Feedback.tenant_id == tenant_id, Feedback.product_id == product_id).order_by(Feedback.id.desc())).all())
