from datetime import datetime
import hashlib
import uuid
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Request,Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.core.config import get_settings
from app.core.evaluation_auth import COOKIE,CurrentPrincipal,issue_session,require_principal,require_product_access,validate_browser_origin
from app.db.session import get_db
from app.models import Company,EvaluationSession,Product,ProductTwinFact,ProductTwinVersion,Regulation,RegulationVersion,LegalUnit,Requirement
from app.api.tenant_agent import analyze as run_tenant_analysis
from app.tenant.agent.schemas import TenantAnalyzeRequest
router=APIRouter(prefix="/v1/evaluation",tags=["Evaluation"])
class Start(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    company_name: str = Field(min_length=1, max_length=200)
    edition: Literal["developer", "enterprise"] = "developer"
class ProductInput(BaseModel): name:str=Field(min_length=1,max_length=200);description:str=Field(default="",max_length=10000);markets:list[str]=Field(default_factory=list);category:str=Field(default="",max_length=100)
def secure(request:Request): return not get_settings().desktop_mode and request.url.scheme=="https" and request.url.hostname not in {"localhost","127.0.0.1"}
@router.post("/start",status_code=201,dependencies=[Depends(validate_browser_origin)])
def start(payload:Start,request:Request,response:Response,db:Session=Depends(get_db)):
    company=Company(name=payload.company_name,industry="",country="",target_markets=[],business_model="evaluation");db.add(company);db.commit();db.refresh(company);session,raw=issue_session(db,company.id,payload.edition);response.set_cookie(COOKIE,raw,httponly=True,samesite="lax",secure=secure(request),path="/",max_age=7*86400);return {"company_id":company.id,"edition":session.edition,"name":payload.name,"email":payload.email,"expires_at":session.expires_at}
@router.get("/me")
def me(principal:CurrentPrincipal=Depends(require_principal)): return {"company_id":principal.company_id,"edition":principal.edition,"session":"evaluation"}
@router.post("/products",status_code=201,dependencies=[Depends(validate_browser_origin)])
def product(payload:ProductInput,principal:CurrentPrincipal=Depends(require_principal),db:Session=Depends(get_db)):
    row=Product(company_id=principal.company_id,name=payload.name,description=payload.description,target_markets=payload.markets,category=payload.category);db.add(row);db.commit();db.refresh(row);return row

_DEMO_REGULATION_NAME = "欧盟 AI 法案（演示条款）"
_DEMO_REGULATION_SHORT_NAME = "欧盟 AI 法案"
_DEMO_REGULATION_AUTHORITY = "欧盟"
_DEMO_UNIT_HEADING = "透明度义务"
_DEMO_REQUIREMENT_SUMMARY = "向用户明确告知其正在与 AI 系统交互"


def _demo_requirement(db: Session) -> Requirement:
    existing = db.scalar(select(Requirement).join(Regulation).where(Regulation.official_identifier == "DATASHIELD-DEMO-AI-TRANSPARENCY"))
    if existing is not None:
        # 旧库中的演示数据可能是英文：命中时同步更新为中文展示文案
        regulation = db.get(Regulation, existing.regulation_id)
        if regulation is not None and (
            regulation.name != _DEMO_REGULATION_NAME
            or regulation.short_name != _DEMO_REGULATION_SHORT_NAME
            or existing.summary != _DEMO_REQUIREMENT_SUMMARY
        ):
            regulation.name = _DEMO_REGULATION_NAME
            regulation.short_name = _DEMO_REGULATION_SHORT_NAME
            regulation.authority = _DEMO_REGULATION_AUTHORITY
            existing.summary = _DEMO_REQUIREMENT_SUMMARY
            unit = db.get(LegalUnit, existing.legal_unit_id) if existing.legal_unit_id else None
            if unit is not None:
                unit.heading = _DEMO_UNIT_HEADING
            db.flush()
        return existing
    regulation = Regulation(name=_DEMO_REGULATION_NAME, short_name=_DEMO_REGULATION_SHORT_NAME, jurisdiction="EU", authority=_DEMO_REGULATION_AUTHORITY, official_identifier="DATASHIELD-DEMO-AI-TRANSPARENCY", canonical_source_url="https://eur-lex.europa.eu/eli/reg/2024/1689/oj")
    db.add(regulation); db.flush()
    text = "Providers shall ensure that persons are informed when they are interacting with an AI system."
    version = RegulationVersion(regulation_id=regulation.id, version_number=1, normalized_text=text, content_hash=hashlib.sha256(text.encode()).hexdigest(), source_url=regulation.canonical_source_url, is_current=True)
    db.add(version); db.flush(); regulation.current_version_id=version.id
    unit = LegalUnit(version_id=version.id, unit_type="article", unit_number="Article 50", heading=_DEMO_UNIT_HEADING, text=text)
    db.add(unit); db.flush()
    requirement = Requirement(regulation_id=regulation.id, version_id=version.id, legal_unit_id=unit.id, requirement_type="obligation", subject_type="provider", action_type="inform", object_type="AI system", conditions_json=[], exceptions_json=[], summary=_DEMO_REQUIREMENT_SUMMARY, confidence=.95, status="ACTIVE")
    db.add(requirement); db.flush(); return requirement

@router.post("/products/{product_id}/initial-review", status_code=201, dependencies=[Depends(validate_browser_origin)])
def initial_review(product_id:int,principal:CurrentPrincipal=Depends(require_principal),db:Session=Depends(get_db)):
    require_product_access(db,product_id,principal)
    requirement=_demo_requirement(db); db.commit()
    return run_tenant_analysis(TenantAnalyzeRequest(tenant_id=principal.company_id,product_id=product_id,trigger_type="MANUAL_SCAN",requirement_ids=[requirement.id]),db,principal)
@router.post("/signout",dependencies=[Depends(validate_browser_origin)])
def signout(response:Response,principal:CurrentPrincipal=Depends(require_principal),db:Session=Depends(get_db)):
    row=db.get(EvaluationSession,principal.session_id);row.revoked_at=datetime.utcnow();db.commit();response.delete_cookie(COOKIE,path="/");return {"signed_out":True}


@router.post("/demo", status_code=201, dependencies=[Depends(validate_browser_origin)])
def demo(request: Request, response: Response, db: Session = Depends(get_db)):
    """Create an isolated, deterministic workspace whose findings use the real domain pipeline."""
    suffix = uuid.uuid4().hex[:10]
    company = Company(name="Acme AI Labs", industry="Software", country="", target_markets=["EU", "US", "UK"], business_model="evaluation")
    db.add(company); db.flush()
    product = Product(company_id=company.id, name="Acme Research Assistant", description="AI-powered SaaS research assistant for uploaded documents.", target_markets=["EU", "US", "UK"], category="AI SaaS")
    db.add(product); db.flush()
    twin = ProductTwinVersion(product_id=product.id, version_number=1, reason="DEMO_SETUP")
    db.add(twin); db.flush()
    facts = [
        ("market_clues", "EU", "PRESENT"), ("market_clues", "US", "PRESENT"), ("market_clues", "UK", "PRESENT"),
        ("subject_types", "provider", "PRESENT"), ("features", "ai_features", "PRESENT"),
        ("features", "user_accounts", "PRESENT"), ("features", "file_upload", "PRESENT"),
        ("features", "subscription", "PRESENT"), ("data_types", "email", "PRESENT"),
        ("data_types", "uploaded_documents", "PRESENT"), ("data_types", "user_queries", "PRESENT"),
        ("controls", "ai_disclosure", "NOT_DETECTED"),
    ]
    for group, name, fact_status in facts:
        db.add(ProductTwinFact(version_id=twin.id, group_name=group, name=name, status=fact_status, confidence=.95 if fact_status == "PRESENT" else .8, source_kind="USER", evidence=[{"type":"USER_DESCRIPTION","reason":"演示工作区初始化时由用户提供"}], scan_scope={"type":"demo_seed"}, confirmation_status="CONFIRMED" if fact_status == "PRESENT" else "UNREVIEWED"))
    requirement = _demo_requirement(db); db.commit()
    session, raw = issue_session(db, company.id, "demo")
    response.set_cookie(COOKIE, raw, httponly=True, samesite="lax", secure=secure(request), path="/", max_age=7*86400)
    principal = CurrentPrincipal(session.id, session.evaluation_user_id, company.id, session.edition)
    result = run_tenant_analysis(TenantAnalyzeRequest(tenant_id=company.id, product_id=product.id, trigger_type="MANUAL_SCAN", requirement_ids=[requirement.id]), db, principal)
    return {"company_id":company.id,"product_id":product.id,"product_name":product.name,"edition":"developer","run_id":result.run_id,"finding_ids":result.finding_ids}
