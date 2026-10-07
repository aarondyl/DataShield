"""Browser-safe facade over Product Understanding and Product Twin APIs.

The shared service credential is resolved and hashed on the server. It is never
accepted from, or returned to, the browser. Domain work remains delegated to the
existing API/service functions.
"""
import hashlib, os
from typing import Literal
from fastapi import APIRouter,BackgroundTasks,Depends,HTTPException,Query
from sqlalchemy.orm import Session
from app.api import product_twin,repository_understanding,website_understanding
from app.db.session import get_db
from app.core.evaluation_auth import CurrentPrincipal, require_company_access, require_principal, require_product_access, validate_browser_origin
from app.understanding.jobs import JobStore,get_store,validate_product_scope
from app.understanding.schemas import AnalysisJob,RepositoryRequest,WebsiteRequest

router=APIRouter(prefix="/v1/ui/understanding",tags=["UI Product Understanding"],dependencies=[Depends(validate_browser_origin)])
def _owner()->str:
    secret=os.getenv("UNDERSTANDING_API_KEY","")
    if not secret: raise HTTPException(503,"Product understanding is not configured")
    return hashlib.sha256(secret.encode()).hexdigest()

@router.post("/website",response_model=AnalysisJob,status_code=202)
def analyze_website(request:WebsiteRequest,background:BackgroundTasks,db:Session=Depends(get_db),store:JobStore=Depends(get_store),principal:CurrentPrincipal=Depends(require_principal)):
    if request.company_id is None or request.product_id is None: raise HTTPException(422,"Product scope is required")
    require_company_access(request.company_id,principal); require_product_access(db,request.product_id,principal)
    return website_understanding.submit(request,background,_owner(),store,db)

@router.post("/repository",response_model=AnalysisJob,status_code=202)
def analyze_repository(request:RepositoryRequest,background:BackgroundTasks,db:Session=Depends(get_db),store:JobStore=Depends(get_store),principal:CurrentPrincipal=Depends(require_principal)):
    if request.company_id is None or request.product_id is None: raise HTTPException(422,"Product scope is required")
    require_company_access(request.company_id,principal); require_product_access(db,request.product_id,principal)
    return repository_understanding.submit(request,background,_owner(),store,db)

@router.get("/analysis/{kind}/{analysis_id}",response_model=AnalysisJob)
def analysis(kind:Literal["website","repository"],analysis_id:str,company_id:int=Query(ge=1),product_id:int=Query(ge=1),db:Session=Depends(get_db),store:JobStore=Depends(get_store),principal:CurrentPrincipal=Depends(require_principal)):
    require_company_access(company_id,principal); require_product_access(db,product_id,principal)
    validate_product_scope(db,company_id,product_id)
    job=store.get(analysis_id,kind,_owner())
    if job.product_id!=product_id: raise HTTPException(404,"Analysis not found for this product")
    return job

@router.get("/products/{product_id}/twin")
def twin(product_id:int,company_id:int=Query(ge=1),db:Session=Depends(get_db),principal:CurrentPrincipal=Depends(require_principal)):
    require_company_access(company_id,principal); require_product_access(db,product_id,principal)
    return product_twin.current(product_id,company_id,db,_owner())

@router.get("/products/{product_id}/twin/versions")
def twin_versions(product_id:int,company_id:int=Query(ge=1),db:Session=Depends(get_db),principal:CurrentPrincipal=Depends(require_principal)):
    require_company_access(company_id,principal); require_product_access(db,product_id,principal)
    return product_twin.versions(product_id,company_id,db,_owner())

@router.post("/products/{product_id}/twin/analyses",status_code=201)
def attach(product_id:int,payload:product_twin.AttachRequest,db:Session=Depends(get_db),store:JobStore=Depends(get_store),principal:CurrentPrincipal=Depends(require_principal)):
    require_company_access(payload.company_id,principal); require_product_access(db,product_id,principal)
    return product_twin.attach(product_id,payload,db,_owner(),store)

@router.post("/products/{product_id}/twin/facts",status_code=201)
def manual_fact(product_id:int,payload:product_twin.ManualFactRequest,db:Session=Depends(get_db),principal:CurrentPrincipal=Depends(require_principal)):
    require_company_access(payload.company_id,principal); require_product_access(db,product_id,principal)
    return product_twin.manual_fact(product_id,payload,db,_owner())

@router.post("/products/{product_id}/twin/facts/{fact_id}/confirm")
def confirm_fact(product_id:int,fact_id:int,payload:product_twin.DecisionRequest,db:Session=Depends(get_db),principal:CurrentPrincipal=Depends(require_principal)):
    require_company_access(payload.company_id,principal); require_product_access(db,product_id,principal)
    return product_twin.confirm(product_id,fact_id,payload,db,_owner())
