"""Email-based account registration/login built on top of evaluation sessions."""
import secrets
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.evaluation_auth import COOKIE, CurrentPrincipal, issue_session, require_principal, validate_browser_origin
from app.core.passwords import hash_password, verify_password
from app.db.session import get_db
from app.models import Company, EvaluationSession, User
from app.services.mailer import get_mailer

router = APIRouter(prefix="/v1/auth", tags=["Auth"])

_CODE_TTL = timedelta(minutes=10)
# user_id -> (code, expires_at)；内存存储，重启即失效
_verification_codes: dict[int, tuple[str, datetime]] = {}


def secure(request: Request):
    return request.url.scheme == "https" and request.url.hostname not in {"localhost", "127.0.0.1"}


class Register(BaseModel):
    email: str = Field(min_length=3, max_length=320, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=200)
    company_name: str = Field(min_length=1, max_length=200)
    edition: Literal["developer", "enterprise"] = "developer"


class Login(BaseModel):
    email: str = Field(min_length=3, max_length=320, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    password: str = Field(min_length=1, max_length=128)


class VerifyEmail(BaseModel):
    code: str = Field(min_length=1, max_length=20)


def _user_payload(user: User):
    return {"user_id": user.id, "email": user.email, "company_id": user.company_id, "edition": user.edition, "email_verified": user.email_verified}


def _set_session_cookie(request: Request, response: Response, db: Session, user: User):
    session, raw = issue_session(db, user.company_id, user.edition, user_id=user.id)
    response.set_cookie(COOKIE, raw, httponly=True, samesite="strict", secure=secure(request), path="/", max_age=get_settings().evaluation_session_days*86400)


def _send_verification_code(user: User):
    code = f"{secrets.randbelow(1000000):06d}"
    _verification_codes[user.id] = (code, datetime.utcnow() + _CODE_TTL)
    get_mailer().send_verification_code(user.email, code)


@router.post("/register", status_code=201, dependencies=[Depends(validate_browser_origin)])
def register(payload: Register, request: Request, response: Response, db: Session = Depends(get_db)):
    email = payload.email.strip().casefold()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "Email already registered")
    company = Company(name=payload.company_name, industry="", country="", target_markets=[], business_model="registered")
    db.add(company); db.flush()
    user = User(email=email, password_hash=hash_password(payload.password), display_name=payload.name.strip(), company_id=company.id, edition=payload.edition)
    db.add(user); db.commit(); db.refresh(user)
    _set_session_cookie(request, response, db, user)
    if get_settings().auth_require_email_verify:
        _send_verification_code(user)
    return _user_payload(user)


@router.post("/login", dependencies=[Depends(validate_browser_origin)])
def login(payload: Login, request: Request, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email.strip().casefold()))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    if user.disabled:
        raise HTTPException(403, "Account disabled")
    user.last_login_at = datetime.utcnow()
    db.commit(); db.refresh(user)
    _set_session_cookie(request, response, db, user)
    return _user_payload(user)


@router.post("/logout", dependencies=[Depends(validate_browser_origin)])
def logout(response: Response, principal: CurrentPrincipal = Depends(require_principal), db: Session = Depends(get_db)):
    row = db.get(EvaluationSession, principal.session_id)
    if row is not None:
        row.revoked_at = datetime.utcnow(); db.commit()
    response.delete_cookie(COOKIE, path="/")
    return {"signed_out": True}


@router.get("/me")
def me(principal: CurrentPrincipal = Depends(require_principal), db: Session = Depends(get_db)):
    row = db.get(EvaluationSession, principal.session_id)
    if row is not None and row.user_id is not None:
        user = db.get(User, row.user_id)
        if user is not None:
            return _user_payload(user)
    return {"session": "evaluation", "company_id": principal.company_id, "edition": principal.edition}


@router.post("/verify-email", dependencies=[Depends(validate_browser_origin)])
def verify_email(payload: VerifyEmail, principal: CurrentPrincipal = Depends(require_principal), db: Session = Depends(get_db)):
    if not get_settings().auth_require_email_verify:
        return {"verified": True, "skipped": True}
    row = db.get(EvaluationSession, principal.session_id)
    user = db.get(User, row.user_id) if row is not None and row.user_id is not None else None
    if user is None:
        raise HTTPException(400, "No registered user for this session")
    record = _verification_codes.get(user.id)
    if record is None or record[1] <= datetime.utcnow() or record[0] != payload.code:
        raise HTTPException(400, "Invalid or expired verification code")
    user.email_verified = True
    db.commit()
    del _verification_codes[user.id]
    return {"verified": True, "skipped": False}
