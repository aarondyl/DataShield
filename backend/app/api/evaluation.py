from datetime import datetime
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Request,Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.evaluation_auth import COOKIE,CurrentPrincipal,get_current_principal,issue_session,require_principal,validate_browser_origin
from app.db.session import get_db
from app.models import Company,EvaluationSession,Product
router=APIRouter(prefix="/v1/evaluation",tags=["Evaluation"])
class Start(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    company_name: str = Field(min_length=1, max_length=200)
    edition: Literal["developer", "enterprise"] = "developer"
class ProductInput(BaseModel): name:str=Field(min_length=1,max_length=200);description:str=Field(default="",max_length=10000);markets:list[str]=Field(default_factory=list);category:str=Field(default="",max_length=100)
def secure(request:Request): return request.url.scheme=="https" and request.url.hostname not in {"localhost","127.0.0.1"}
@router.post("/start",status_code=201,dependencies=[Depends(validate_browser_origin)])
def start(payload:Start,request:Request,response:Response,db:Session=Depends(get_db)):
    company=Company(name=payload.company_name,industry="",country="",target_markets=[],business_model="evaluation");db.add(company);db.commit();db.refresh(company);session,raw=issue_session(db,company.id,payload.edition);response.set_cookie(COOKIE,raw,httponly=True,samesite="lax",secure=secure(request),path="/",max_age=7*86400);return {"company_id":company.id,"edition":session.edition,"name":payload.name,"email":payload.email,"expires_at":session.expires_at}
@router.get("/me")
def me(principal:CurrentPrincipal=Depends(require_principal)): return {"company_id":principal.company_id,"edition":principal.edition,"session":"evaluation"}
@router.post("/products",status_code=201,dependencies=[Depends(validate_browser_origin)])
def product(payload:ProductInput,principal:CurrentPrincipal=Depends(require_principal),db:Session=Depends(get_db)):
    row=Product(company_id=principal.company_id,name=payload.name,description=payload.description,target_markets=payload.markets,category=payload.category);db.add(row);db.commit();db.refresh(row);return row
@router.post("/signout",dependencies=[Depends(validate_browser_origin)])
def signout(response:Response,principal:CurrentPrincipal=Depends(require_principal),db:Session=Depends(get_db)):
    row=db.get(EvaluationSession,principal.session_id);row.revoked_at=datetime.utcnow();db.commit();response.delete_cookie(COOKIE,path="/");return {"signed_out":True}
