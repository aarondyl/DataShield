"""Apply confirmed fact corrections as append-only Product Twin versions."""
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import ProductTwinFact, ProductTwinVersion
from app.tenant.feedback.schemas import CandidateStatus
from app.tenant.feedback.service import FeedbackConflictError, owned_candidate
from app.understanding.schemas import Fact, FindingStatus
from app.understanding.twin import decide_fact

def resolve_active_lineage_fact(db:Session,product_id:int,target_fact_id:int)->ProductTwinFact:
    target=db.get(ProductTwinFact,target_fact_id)
    if not target: raise FeedbackConflictError("Target fact does not exist")
    origin=db.get(ProductTwinVersion,target.version_id)
    if not origin or origin.product_id!=product_id: raise FeedbackConflictError("Target fact is outside product")
    current=db.scalar(select(ProductTwinVersion).where(ProductTwinVersion.product_id==product_id).order_by(ProductTwinVersion.version_number.desc()).limit(1))
    if not current: raise FeedbackConflictError("Product Twin has no current version")
    candidates=list(db.scalars(select(ProductTwinFact).where(ProductTwinFact.version_id==current.id,ProductTwinFact.group_name==target.group_name,ProductTwinFact.name==target.name,ProductTwinFact.confirmation_status!="CORRECTED")).all())
    if len(candidates)!=1: raise FeedbackConflictError("Fact lineage has no unique active descendant")
    return candidates[0]

def apply_confirmed_feedback_candidate(db:Session,tenant_id:int,candidate_id:int):
    candidate=owned_candidate(db,tenant_id,candidate_id)
    if candidate.status!=CandidateStatus.CONFIRMED.value: raise FeedbackConflictError("Only a CONFIRMED candidate can be applied")
    if candidate.applied_fact_id and candidate.applied_twin_version_id: return candidate
    if not candidate.target_fact_id or not candidate.proposed_name or not candidate.proposed_status: raise FeedbackConflictError("Correction candidate is incomplete")
    active=resolve_active_lineage_fact(db,candidate.product_id,candidate.target_fact_id)
    version=decide_fact(db,candidate.product_id,active.id,"CORRECT","Confirmed user feedback", "feedback-loop",
        Fact(name=candidate.proposed_name,status=FindingStatus(candidate.proposed_status),confidence=candidate.confidence,evidence_ids=[]))
    new_fact=db.scalar(select(ProductTwinFact).where(ProductTwinFact.version_id==version.id,ProductTwinFact.supersedes_fact_id==active.id).order_by(ProductTwinFact.id.desc()))
    candidate=db.get(type(candidate),candidate.id); candidate.applied_fact_id=new_fact.id; candidate.applied_twin_version_id=version.id; candidate.last_error=""
    db.commit(); db.refresh(candidate); return candidate
