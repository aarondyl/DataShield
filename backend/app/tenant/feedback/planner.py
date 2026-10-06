"""Structured interpretation of immutable user feedback."""
import json
from pydantic import ValidationError
from sqlalchemy.orm import Session
from app.core.llm import BaseLLMClient, LLMError, get_llm_client
from app.models import FeedbackCandidate
from app.tenant.context.service import load_product_context
from app.tenant.feedback.schemas import CandidateStatus, FactCorrectionProposal, FeedbackCreateRequest
from app.tenant.feedback.service import attach_candidate, create_feedback, owned_candidate

class FeedbackPlanningError(ValueError): pass
class FeedbackProviderError(RuntimeError): pass
PROMPT_VERSION="feedback-candidate-v1"
SYSTEM="""Interpret feedback only as a candidate. Never update state, invent product facts, legal references, or treat UNKNOWN as false. Return JSON only. If ambiguous, ask one discriminating question."""

def _context(db, request):
    product=load_product_context(db,request.tenant_id,request.product_id)
    return {"task":"feedback-candidate","raw_feedback":request.raw_text,"facts":[f.model_dump(mode="json") for f in product.facts]}

def submit_feedback(db:Session,request:FeedbackCreateRequest,*,llm:BaseLLMClient|None=None):
    feedback,_=create_feedback(db,request)
    client=llm or get_llm_client(); context=_context(db,request)
    try: raw=client.chat_json(SYSTEM,json.dumps(context,ensure_ascii=False),context=context)
    except Exception as exc: raise FeedbackProviderError("Feedback model provider failed") from exc
    try: proposal=FactCorrectionProposal.model_validate(raw)
    except ValidationError as exc: raise FeedbackPlanningError("Invalid structured feedback proposal") from exc
    candidate=attach_candidate(db,feedback,proposal,model_provider=client.provider_name,model_name=client.model_name,prompt_version=PROMPT_VERSION)
    return feedback,candidate

def clarify_candidate(db:Session,tenant_id:int,candidate_id:int,answer:str,*,llm:BaseLLMClient|None=None):
    row=owned_candidate(db,tenant_id,candidate_id)
    if row.status != CandidateStatus.NEEDS_CLARIFICATION.value: raise FeedbackPlanningError("Candidate does not need clarification")
    feedback=row.feedback; request=FeedbackCreateRequest(tenant_id=tenant_id,product_id=row.product_id,finding_id=feedback.finding_id,remediation_id=feedback.remediation_id,feedback_type=feedback.feedback_type,raw_text=feedback.raw_text,created_by=feedback.created_by,useful=feedback.useful,negative_reason=feedback.negative_reason)
    context=_context(db,request); context["clarification_question"]=row.clarification_question; context["clarification_answer"]=answer
    client=llm or get_llm_client()
    try: proposal=FactCorrectionProposal.model_validate(client.chat_json(SYSTEM,json.dumps(context,ensure_ascii=False),context=context))
    except LLMError as exc: raise FeedbackProviderError("Feedback model provider failed") from exc
    except ValidationError as exc: raise FeedbackPlanningError("Invalid structured feedback proposal") from exc
    if proposal.needs_clarification: raise FeedbackPlanningError("Clarification did not resolve candidate")
    row.target_fact_id=proposal.target_fact_id; row.proposed_name=proposal.proposed_name; row.proposed_value=proposal.proposed_value; row.proposed_status=proposal.proposed_status.value; row.reasoning_summary=proposal.reasoning_summary; row.confidence=proposal.confidence; row.clarification_answer=answer; row.clarification_question=None; row.status=CandidateStatus.PROPOSED.value
    db.commit(); db.refresh(row); return row
