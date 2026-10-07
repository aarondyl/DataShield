"""Tenant-scoped Feedback Loop API."""
from fastapi import APIRouter,Depends,HTTPException,Query,status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.evaluation_auth import CurrentPrincipal, require_company_access, require_principal, require_product_access, validate_browser_origin
from app.core.llm import MockLLMClient
from app.tenant.feedback.planner import FeedbackPlanningError,FeedbackProviderError,clarify_candidate,submit_feedback
from app.tenant.feedback.product_twin import apply_confirmed_feedback_candidate
from app.tenant.feedback.reanalysis import reanalyze_confirmed_candidate
from app.tenant.feedback.schemas import CandidateDecisionRequest,CandidateRecord,CandidateStatus,ClarificationRequest,FeedbackCreateRequest,FeedbackSubmission
from app.tenant.feedback.service import FeedbackConflictError,FeedbackGroundingError,FeedbackNotFoundError,candidate_record,feedback_record,get_feedback,list_feedback,owned_candidate,set_candidate_status

router=APIRouter(prefix="/v1",tags=["Tenant Feedback"],dependencies=[Depends(validate_browser_origin)])
def fail(exc):
    if isinstance(exc,FeedbackNotFoundError): return HTTPException(404,str(exc))
    if isinstance(exc,FeedbackConflictError): return HTTPException(409,str(exc))
    if isinstance(exc,FeedbackProviderError): return HTTPException(502,str(exc))
    if isinstance(exc,(FeedbackGroundingError,FeedbackPlanningError,ValueError)): return HTTPException(422,str(exc))
    return HTTPException(500,"Feedback operation failed")

@router.post("/feedback",response_model=FeedbackSubmission,status_code=status.HTTP_201_CREATED)
def create(payload:FeedbackCreateRequest,db:Session=Depends(get_db),principal:CurrentPrincipal=Depends(require_principal)):
    require_company_access(payload.tenant_id,principal); require_product_access(db,payload.product_id,principal)
    try:
        row,candidate=submit_feedback(db,payload,llm=MockLLMClient() if principal.edition=="demo" else None)
        return FeedbackSubmission(feedback=feedback_record(row),candidates=[candidate_record(db,candidate)])
    except Exception as exc: raise fail(exc) from exc

@router.get("/feedback/{feedback_id}",response_model=FeedbackSubmission)
def detail(feedback_id:int,tenant_id:int=Query(ge=1),db:Session=Depends(get_db),principal:CurrentPrincipal=Depends(require_principal)):
    require_company_access(tenant_id,principal)
    try:
        row=get_feedback(db,tenant_id,feedback_id)
        return FeedbackSubmission(feedback=feedback_record(row),candidates=[candidate_record(db,c) for c in row.candidates])
    except Exception as exc: raise fail(exc) from exc

@router.get("/feedback-candidates/{candidate_id}",response_model=CandidateRecord)
def candidate_detail(candidate_id:int,tenant_id:int=Query(ge=1),db:Session=Depends(get_db),principal:CurrentPrincipal=Depends(require_principal)):
    require_company_access(tenant_id,principal)
    try: return candidate_record(db,owned_candidate(db,tenant_id,candidate_id))
    except Exception as exc: raise fail(exc) from exc

@router.post("/feedback-candidates/{candidate_id}/clarify",response_model=CandidateRecord)
def clarify(candidate_id:int,payload:ClarificationRequest,db:Session=Depends(get_db),principal:CurrentPrincipal=Depends(require_principal)):
    require_company_access(payload.tenant_id,principal)
    try: return candidate_record(db,clarify_candidate(db,payload.tenant_id,candidate_id,payload.answer,llm=MockLLMClient() if principal.edition=="demo" else None))
    except Exception as exc: raise fail(exc) from exc

def decide(candidate_id,payload,db,target):
    try: return candidate_record(db,set_candidate_status(db,payload.tenant_id,candidate_id,target))
    except Exception as exc: raise fail(exc) from exc
@router.post("/feedback-candidates/{candidate_id}/confirm",response_model=CandidateRecord)
def confirm(candidate_id:int,payload:CandidateDecisionRequest,db:Session=Depends(get_db),principal:CurrentPrincipal=Depends(require_principal)): require_company_access(payload.tenant_id,principal); return decide(candidate_id,payload,db,CandidateStatus.CONFIRMED)
@router.post("/feedback-candidates/{candidate_id}/reject",response_model=CandidateRecord)
def reject(candidate_id:int,payload:CandidateDecisionRequest,db:Session=Depends(get_db),principal:CurrentPrincipal=Depends(require_principal)): require_company_access(payload.tenant_id,principal); return decide(candidate_id,payload,db,CandidateStatus.REJECTED)

@router.post("/feedback-candidates/{candidate_id}/apply",response_model=CandidateRecord)
def apply(candidate_id:int,payload:CandidateDecisionRequest,db:Session=Depends(get_db),principal:CurrentPrincipal=Depends(require_principal)):
    require_company_access(payload.tenant_id,principal)
    try:
        row=apply_confirmed_feedback_candidate(db,payload.tenant_id,candidate_id)
        return candidate_record(db,reanalyze_confirmed_candidate(db,payload.tenant_id,row.id))
    except Exception as exc: raise fail(exc) from exc

@router.get("/products/{product_id}/feedback",response_model=list[FeedbackSubmission])
def product_feedback(product_id:int,tenant_id:int=Query(ge=1),db:Session=Depends(get_db),principal:CurrentPrincipal=Depends(require_principal)):
    require_company_access(tenant_id,principal); require_product_access(db,product_id,principal)
    try: return [FeedbackSubmission(feedback=feedback_record(r),candidates=[candidate_record(db,c) for c in r.candidates]) for r in list_feedback(db,tenant_id,product_id)]
    except Exception as exc: raise fail(exc) from exc
