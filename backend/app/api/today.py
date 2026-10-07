"""Tenant-scoped presentation read model for Today."""
from datetime import datetime
from typing import Any
from fastapi import APIRouter,Depends,Query
from pydantic import BaseModel,Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.evaluation_auth import CurrentPrincipal, require_company_access, require_principal
from app.models import Feedback,FeedbackCandidate,Finding,Remediation,TenantAgentRun,TenantMissingContextItem
from app.tenant.context.ownership import resolve_tenant_product
router=APIRouter(prefix="/v1/today",tags=["Tenant Today"])
class AttentionItem(BaseModel):
    id:str; type:str; title:str; summary:str; severity:str|None=None; status:str; product_id:int; created_at:datetime|None=None; target_route:str; target:dict[str,Any]=Field(default_factory=dict)
class TodayResponse(BaseModel):
    needs_review:list[AttentionItem]=Field(default_factory=list); waiting_for_you:list[AttentionItem]=Field(default_factory=list); recently_completed:list[AttentionItem]=Field(default_factory=list)
@router.get("",response_model=TodayResponse)
def today(tenant_id:int=Query(ge=1),product_id:int=Query(ge=1),db:Session=Depends(get_db),principal:CurrentPrincipal=Depends(require_principal)):
    require_company_access(tenant_id, principal)
    resolve_tenant_product(db,tenant_id,product_id); out=TodayResponse()
    superseded_finding_ids=set()
    applied=db.scalars(select(FeedbackCandidate).join(Feedback,Feedback.id==FeedbackCandidate.feedback_id).where(FeedbackCandidate.tenant_id==tenant_id,FeedbackCandidate.product_id==product_id,FeedbackCandidate.status=="APPLIED",Feedback.finding_id.is_not(None))).all()
    for candidate in applied:
        rerun=db.get(TenantAgentRun,candidate.reanalysis_run_id) if candidate.reanalysis_run_id else None
        if rerun and not (rerun.output_json or {}).get("finding_ids"):
            superseded_finding_ids.add(candidate.feedback.finding_id)
    for f in db.scalars(select(Finding).where(Finding.tenant_id==tenant_id,Finding.product_id==product_id).order_by(Finding.created_at.desc())).all():
        if f.id in superseded_finding_ids: continue
        item=AttentionItem(id=f"finding:{f.id}",type="FINDING",title=f.title,summary=f.gap_summary,severity=f.impact_level,status=f.status,product_id=product_id,created_at=f.created_at,target_route=f"/app/findings/{f.id}",target={"finding_id":f.id})
        (out.needs_review if f.status=="OPEN" else out.recently_completed).append(item)
    runs=db.scalars(select(TenantAgentRun).where(TenantAgentRun.tenant_id==tenant_id,TenantAgentRun.product_id==product_id)).all(); run_ids=[r.id for r in runs]
    if run_ids:
        for m in db.scalars(select(TenantMissingContextItem).where(TenantMissingContextItem.run_id.in_(run_ids),TenantMissingContextItem.status=="OPEN")).all(): out.waiting_for_you.append(AttentionItem(id=f"context:{m.id}",type="MISSING_CONTEXT",title="DataShield needs one detail",summary=m.question,status="NEEDS_USER_INPUT",product_id=product_id,created_at=m.created_at,target_route="/app/product",target={"run_id":m.run_id,"requirement_id":m.requirement_id,"field_path":m.field_path}))
    for r in db.scalars(select(Remediation).where(Remediation.tenant_id==tenant_id,Remediation.product_id==product_id).order_by(Remediation.created_at.desc())).all():
        item=AttentionItem(id=f"remediation:{r.id}",type="REMEDIATION",title=r.title,summary=r.summary,status=r.status,product_id=product_id,created_at=r.created_at,target_route=f"/app/actions/{r.id}",target={"remediation_id":r.id,"finding_id":r.finding_id}); (out.waiting_for_you if r.status=="PROPOSED" else out.recently_completed).append(item)
    for c in db.scalars(select(FeedbackCandidate).where(FeedbackCandidate.tenant_id==tenant_id,FeedbackCandidate.product_id==product_id).order_by(FeedbackCandidate.created_at.desc())).all():
        item=AttentionItem(id=f"candidate:{c.id}",type="FEEDBACK_CANDIDATE",title="Confirm what DataShield understood",summary=c.clarification_question or c.reasoning_summary,status=c.status,product_id=product_id,created_at=c.created_at,target_route="/app/product",target={"candidate_id":c.id,"feedback_id":c.feedback_id}); (out.waiting_for_you if c.status in {"PROPOSED","NEEDS_CLARIFICATION","CONFIRMED"} else out.recently_completed).append(item)
    return out
