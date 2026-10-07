"""Server-enforced identity and lightweight Origin validation for evaluation UI."""
import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime,timedelta
from fastapi import Cookie,Depends,HTTPException,Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models import EvaluationSession,Product
from app.core.config import get_settings
COOKIE="datashield_evaluation"
@dataclass(frozen=True)
class CurrentPrincipal: session_id:int; user_id:str; company_id:int; edition:str
def token_hash(token:str)->str:return hashlib.sha256(token.encode()).hexdigest()
def issue_session(db:Session,company_id:int,edition:str):
    raw=secrets.token_urlsafe(48)
    row=EvaluationSession(token_hash=token_hash(raw),evaluation_user_id=secrets.token_hex(16),company_id=company_id,edition=edition,expires_at=datetime.utcnow()+timedelta(days=get_settings().evaluation_session_days))
    db.add(row);db.commit();db.refresh(row);return row,raw
def get_current_principal(datashield_evaluation:str|None=Cookie(default=None),db:Session=Depends(get_db)):
    if not datashield_evaluation: return None
    row=db.scalar(select(EvaluationSession).where(EvaluationSession.token_hash==token_hash(datashield_evaluation)))
    if not row or row.revoked_at or row.expires_at<=datetime.utcnow(): return None
    return CurrentPrincipal(row.id,row.evaluation_user_id,row.company_id,row.edition)
def require_principal(principal:CurrentPrincipal|None=Depends(get_current_principal)):
    if principal is None: raise HTTPException(401,"Evaluation session required")
    return principal
def require_company_access(requested:int,principal:CurrentPrincipal):
    if requested!=principal.company_id: raise HTTPException(404,"Resource not found")
def require_product_access(db:Session,product_id:int,principal:CurrentPrincipal):
    product=db.get(Product,product_id)
    if not product or product.company_id!=principal.company_id: raise HTTPException(404,"Resource not found")
    return product
def validate_browser_origin(request:Request):
    if request.method in {"GET","HEAD","OPTIONS"}: return
    origin=request.headers.get("origin")
    allowed={x.strip() for x in get_settings().application_origins.split(",") if x.strip()}
    if origin not in allowed: raise HTTPException(403,"Request origin is not allowed")
