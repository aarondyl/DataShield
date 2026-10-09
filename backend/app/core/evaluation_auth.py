"""Server-enforced identity and lightweight Origin validation for evaluation UI."""
import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime,timedelta
from fastapi import Cookie,Depends,HTTPException,Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models import EvaluationSession,Product,User
from app.core.config import get_settings
COOKIE="datashield_evaluation"
@dataclass(frozen=True)
class CurrentPrincipal: session_id:int; user_id:str; company_id:int; edition:str
def token_hash(token:str)->str:return hashlib.sha256(token.encode()).hexdigest()
def issue_session(db:Session,company_id:int,edition:str,user_id:int|None=None):
    raw=secrets.token_urlsafe(48)
    row=EvaluationSession(token_hash=token_hash(raw),evaluation_user_id=secrets.token_hex(16),company_id=company_id,edition=edition,user_id=user_id,expires_at=datetime.utcnow()+timedelta(days=get_settings().evaluation_session_days))
    db.add(row);db.commit();db.refresh(row);return row,raw
def get_current_principal(datashield_evaluation:str|None=Cookie(default=None),db:Session=Depends(get_db)):
    if not datashield_evaluation: return None
    row=db.scalar(select(EvaluationSession).where(EvaluationSession.token_hash==token_hash(datashield_evaluation)))
    if not row or row.revoked_at or row.expires_at<=datetime.utcnow(): return None
    return CurrentPrincipal(row.id,row.evaluation_user_id,row.company_id,row.edition)
def require_principal(principal:CurrentPrincipal|None=Depends(get_current_principal),db:Session=Depends(get_db)):
    if principal is None and get_settings().evaluation_auth_bypass:
        return CurrentPrincipal(0, "automated-test", 0, "developer")
    if principal is None: raise HTTPException(401,"Evaluation session required")
    row=db.get(EvaluationSession,principal.session_id) if principal.session_id else None
    user=db.get(User,row.user_id) if row is not None and row.user_id is not None else None
    if row is not None and row.user_id is not None and (user is None or user.disabled):
        raise HTTPException(403,"Account disabled")
    return principal
def require_company_access(requested:int,principal:CurrentPrincipal):
    if principal.session_id == 0 and get_settings().evaluation_auth_bypass: return
    if requested!=principal.company_id: raise HTTPException(404,"Resource not found")
def require_product_access(db:Session,product_id:int,principal:CurrentPrincipal):
    product=db.get(Product,product_id)
    if product and principal.session_id == 0 and get_settings().evaluation_auth_bypass: return product
    if not product or product.company_id!=principal.company_id: raise HTTPException(404,"Resource not found")
    return product
def validate_browser_origin(request:Request):
    if request.method in {"GET","HEAD","OPTIONS"}: return
    if get_settings().evaluation_auth_bypass: return
    origin=request.headers.get("origin")
    allowed={x.strip() for x in get_settings().application_origins.split(",") if x.strip()}
    if origin not in allowed: raise HTTPException(403,"Request origin is not allowed")
