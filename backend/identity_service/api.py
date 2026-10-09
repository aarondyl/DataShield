"""Cloud account, device-session and organization APIs.

The service accepts bearer tokens only, stores opaque token hashes, and never
mounts Product, Finding, Evidence or other tenant business APIs.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import json
import re
import secrets
import threading
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, Header, HTTPException, Request
import httpx
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.passwords import hash_password, verify_password
from identity_service.database import get_db
from identity_service.mailer import send_security_code
from identity_service.models import (
    IdentityAuditEvent, IdentitySession, IdentityUser, LoginAttempt, Membership,
    Organization, OrganizationInvitation, PasswordResetToken, VerificationToken,
)
from identity_service.settings import IdentitySettings


router = APIRouter(prefix="/v1", tags=["Identity"])
_EMAIL_CODE = re.compile(r"^\d{6}$")
_EMAIL_PATTERN = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
_ai_lock = threading.Lock()
_ai_calls: dict[int, deque[datetime]] = defaultdict(deque)


class AIChatRequest(BaseModel):
    system_prompt: str = Field(min_length=1, max_length=12_000)
    user_prompt: str = Field(min_length=1, max_length=48_000)


def _limit_ai_calls(user_id: int) -> None:
    now = datetime.now(UTC)
    with _ai_lock:
        calls = _ai_calls[user_id]
        while calls and (now - calls[0]).total_seconds() > 60:
            calls.popleft()
        if len(calls) >= 12:
            raise HTTPException(429, "AI request limit reached. Try again shortly.",
                                headers={"Retry-After": "60"})
        calls.append(now)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _email_key(email: str) -> str:
    return _hash(email.strip().casefold())


def _ip_key(request: Request) -> str:
    # The published Identity port is loopback-only behind the host reverse
    # proxy. Use the right-most forwarded value, which Nginx appends from its
    # observed peer address; earlier client-supplied values are ignored.
    forwarded = request.headers.get("x-forwarded-for", "")
    observed = forwarded.split(",")[-1].strip() if forwarded else ""
    return _hash(observed or (request.client.host if request.client else "unknown"))


def _rate_limit(db: Session, email: str, ip_key: str, settings: IdentitySettings, *,
                purpose: str = "auth", include_success: bool = False) -> None:
    since = _now() - timedelta(minutes=settings.login_window_minutes)
    filters = [
        LoginAttempt.created_at >= since,
        (LoginAttempt.email_key == _email_key(email)) | (LoginAttempt.ip_key == ip_key),
        LoginAttempt.purpose == purpose,
    ]
    if not include_success:
        filters.append(LoginAttempt.succeeded.is_(False))
    count = db.scalar(select(func.count()).select_from(LoginAttempt).where(*filters)) or 0
    if count >= settings.login_max_attempts:
        raise HTTPException(429, "Too many authentication attempts. Try again later.",
                            headers={"Retry-After": str(settings.login_window_minutes * 60)})


def _record_attempt(db: Session, email: str, ip_key: str, succeeded: bool, *, purpose: str = "auth") -> None:
    db.query(LoginAttempt).filter(LoginAttempt.created_at < _now() - timedelta(days=1)).delete()
    db.add(LoginAttempt(email_key=_email_key(email), ip_key=ip_key, succeeded=succeeded, purpose=purpose))
    db.commit()


def _issue_session(db: Session, user: IdentityUser, organization_id: int, device_name: str, settings: IdentitySettings) -> dict:
    access = secrets.token_urlsafe(48)
    refresh = secrets.token_urlsafe(64)
    now = _now()
    session = IdentitySession(
        user_id=user.id,
        organization_id=organization_id,
        access_token_hash=_hash(access),
        refresh_token_hash=_hash(refresh),
        device_name=device_name[:200],
        access_expires_at=now + timedelta(minutes=settings.access_minutes),
        refresh_expires_at=now + timedelta(days=settings.refresh_days),
        last_used_at=now,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "Bearer",
        "expires_in": settings.access_minutes * 60,
        "session_id": session.id,
        "organization_id": organization_id,
    }


@dataclass(frozen=True)
class Principal:
    user: IdentityUser
    session: IdentitySession
    membership: Membership


def require_principal(
    authorization: str | None = Header(default=None), db: Session = Depends(get_db)
) -> Principal:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(401, "Bearer access token required")
    session = db.scalar(select(IdentitySession).where(IdentitySession.access_token_hash == _hash(token)))
    now = _now()
    if session is None or session.revoked_at or session.access_expires_at <= now or session.refresh_expires_at <= now:
        raise HTTPException(401, "Session expired or revoked")
    user = db.get(IdentityUser, session.user_id)
    membership = db.scalar(select(Membership).where(
        Membership.user_id == session.user_id,
        Membership.organization_id == session.organization_id,
    ))
    if user is None or user.disabled:
        raise HTTPException(403, "Account disabled")
    if membership is None:
        raise HTTPException(403, "Organization membership required")
    session.last_used_at = now
    db.commit()
    return Principal(user, session, membership)


def require_roles(*roles: str):
    def check(principal: Principal = Depends(require_principal)) -> Principal:
        if principal.membership.role not in roles:
            raise HTTPException(403, "Insufficient organization role")
        return principal
    return check


def require_platform_admin(principal: Principal = Depends(require_principal)) -> Principal:
    if not principal.user.is_platform_admin:
        raise HTTPException(403, "Platform administrator access required")
    return principal


@router.post("/ai/chat-json")
async def cloud_ai_chat_json(payload: AIChatRequest,
                             principal: Principal = Depends(require_principal)):
    """Authenticated, rate-limited DataShield inference; prompts are never logged."""
    settings = IdentitySettings.load()
    if not settings.llm_api_key:
        raise HTTPException(503, "DataShield Cloud AI is not configured")
    _limit_ai_calls(principal.user.id)
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(45.0, connect=8.0), follow_redirects=False) as client:
            response = await client.post(
                "https://api.deepseek.com/chat/completions",
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                json={
                    "model": settings.llm_model,
                    "messages": [
                        {"role": "system", "content": payload.system_prompt},
                        {"role": "user", "content": payload.user_prompt},
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.2,
                    "max_tokens": 4096,
                },
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
        value = json.loads(content)
        if not isinstance(value, dict):
            raise ValueError("model response must be a JSON object")
    except HTTPException:
        raise
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError):
        raise HTTPException(502, "Cloud AI inference failed or returned invalid structured output") from None
    return {"provider": "deepseek", "model": settings.llm_model, "result": value}



class RegisterInput(BaseModel):
    email: str = Field(pattern=_EMAIL_PATTERN, max_length=320)
    password: str = Field(min_length=12, max_length=128)
    name: str = Field(min_length=1, max_length=200)
    organization_name: str = Field(min_length=1, max_length=200)
    edition: str = Field(default="developer", pattern="^(developer|enterprise)$")


class LoginInput(BaseModel):
    email: str = Field(pattern=_EMAIL_PATTERN, max_length=320)
    password: str = Field(min_length=1, max_length=128)
    device_name: str = Field(default="DataShield Desktop", max_length=200)


class RefreshInput(BaseModel):
    refresh_token: str = Field(min_length=32, max_length=256)


class CodeInput(BaseModel):
    email: str = Field(pattern=_EMAIL_PATTERN, max_length=320)
    code: str = Field(min_length=6, max_length=6)


class EmailInput(BaseModel):
    email: str = Field(pattern=_EMAIL_PATTERN, max_length=320)


class PasswordResetConfirm(BaseModel):
    email: str = Field(pattern=_EMAIL_PATTERN, max_length=320)
    code: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=12, max_length=128)


class OrganizationInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    edition: str = Field(default="developer", pattern="^(developer|enterprise)$")


class InvitationInput(BaseModel):
    email: str = Field(pattern=_EMAIL_PATTERN, max_length=320)
    role: str = Field(default="member", pattern="^(admin|member)$")


class AcceptInvitationInput(BaseModel):
    code: str = Field(min_length=32, max_length=256)


class RoleInput(BaseModel):
    role: str = Field(pattern="^(admin|member)$")


class AccountStatusInput(BaseModel):
    disabled: bool


def _send_code(settings: IdentitySettings, email: str, purpose: str, code: str) -> None:
    try:
        send_security_code(settings, email, purpose, code)
    except Exception as exc:
        raise HTTPException(503, "Identity email delivery is unavailable") from exc


def _new_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _replace_verification_token(db: Session, user: IdentityUser, settings: IdentitySettings) -> None:
    db.query(VerificationToken).filter(
        VerificationToken.user_id == user.id,
        VerificationToken.used_at.is_(None),
    ).update({VerificationToken.used_at: _now()})
    code = _new_code()
    db.add(VerificationToken(user_id=user.id, token_hash=_hash(code),
                             expires_at=_now() + timedelta(minutes=settings.email_code_minutes)))
    db.commit()
    _send_code(settings, user.email, "account verification", code)


def _audit(db: Session, action: str, actor: int | None, organization_id: int | None = None,
           target_user_id: int | None = None) -> None:
    db.add(IdentityAuditEvent(actor_user_id=actor, organization_id=organization_id,
                              action=action, target_user_id=target_user_id))
    db.commit()


def _user_view(user: IdentityUser, organization: Organization, role: str) -> dict:
    return {
        "user_id": user.id, "email": user.email, "name": user.display_name,
        "email_verified": user.email_verified,
        "organization": {"id": organization.id, "name": organization.name,
                         "edition": organization.edition, "role": role},
    }


@router.post("/auth/register", status_code=201)
def register(payload: RegisterInput, request: Request, db: Session = Depends(get_db)):
    settings = IdentitySettings.load()
    if settings.email_verify_required and not settings.email_ready:
        raise HTTPException(503, "Identity email verification is not configured")
    email = str(payload.email).strip().casefold()
    ip = _ip_key(request)
    _rate_limit(db, email, ip, settings)
    if db.scalar(select(IdentityUser).where(IdentityUser.email == email)):
        _record_attempt(db, email, ip, False)
        raise HTTPException(409, "Email already registered")
    organization = Organization(name=payload.organization_name.strip(), edition=payload.edition)
    user = IdentityUser(email=email, password_hash=hash_password(payload.password),
                        display_name=payload.name.strip(), email_verified=not settings.email_verify_required)
    db.add_all([organization, user])
    db.flush()
    db.add(Membership(organization_id=organization.id, user_id=user.id, role="owner"))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Email already registered") from None
    db.refresh(user)
    db.refresh(organization)
    _record_attempt(db, email, ip, True)
    _audit(db, "account.registered", user.id, organization.id, user.id)
    if settings.email_verify_required:
        _replace_verification_token(db, user, settings)
        return {"verification_required": True, "email": email}
    return {**_user_view(user, organization, "owner"),
            **_issue_session(db, user, organization.id, "DataShield Desktop", settings)}


@router.post("/auth/verify-email")
def verify_email(payload: CodeInput, request: Request, db: Session = Depends(get_db)):
    email = str(payload.email).strip().casefold()
    settings = IdentitySettings.load()
    ip = _ip_key(request)
    _rate_limit(db, email, ip, settings, purpose="verify")
    user = db.scalar(select(IdentityUser).where(IdentityUser.email == email))
    if user is None:
        _record_attempt(db, email, ip, False, purpose="verify")
        raise HTTPException(400, "Invalid or expired verification code")
    token = db.scalar(select(VerificationToken).where(
        VerificationToken.user_id == user.id,
        VerificationToken.token_hash == _hash(payload.code),
        VerificationToken.used_at.is_(None),
        VerificationToken.expires_at > _now(),
    ))
    if token is None or not _EMAIL_CODE.fullmatch(payload.code):
        _record_attempt(db, email, ip, False, purpose="verify")
        raise HTTPException(400, "Invalid or expired verification code")
    token.used_at = _now()
    user.email_verified = True
    db.commit()
    _record_attempt(db, email, ip, True, purpose="verify")
    return {"verified": True}


@router.post("/auth/verification/resend")
def resend_verification(payload: EmailInput, request: Request, db: Session = Depends(get_db)):
    settings = IdentitySettings.load()
    if not settings.email_ready:
        raise HTTPException(503, "Identity email delivery is not configured")
    email = str(payload.email).strip().casefold()
    ip = _ip_key(request)
    _rate_limit(db, email, ip, settings, purpose="verify_resend", include_success=True)
    user = db.scalar(select(IdentityUser).where(IdentityUser.email == email, IdentityUser.email_verified.is_(False)))
    if user:
        _replace_verification_token(db, user, settings)
    _record_attempt(db, email, ip, False, purpose="verify_resend")
    return {"requested": True}


@router.post("/auth/login")
def login(payload: LoginInput, request: Request, db: Session = Depends(get_db)):
    settings = IdentitySettings.load()
    email = str(payload.email).strip().casefold()
    ip = _ip_key(request)
    _rate_limit(db, email, ip, settings)
    user = db.scalar(select(IdentityUser).where(IdentityUser.email == email))
    if user is None or user.disabled or not verify_password(payload.password, user.password_hash):
        _record_attempt(db, email, ip, False)
        raise HTTPException(401, "Invalid email or password")
    if settings.email_verify_required and not user.email_verified:
        _record_attempt(db, email, ip, False)
        raise HTTPException(403, "Email verification required")
    membership = db.scalar(select(Membership).where(Membership.user_id == user.id).order_by(Membership.id))
    if membership is None:
        _record_attempt(db, email, ip, False)
        raise HTTPException(403, "Organization membership required")
    organization = db.get(Organization, membership.organization_id)
    user.last_login_at = _now()
    db.commit()
    _record_attempt(db, email, ip, True)
    return {**_user_view(user, organization, membership.role),
            **_issue_session(db, user, organization.id, payload.device_name, settings)}


@router.post("/auth/refresh")
def refresh(payload: RefreshInput, db: Session = Depends(get_db)):
    settings = IdentitySettings.load()
    session = db.scalar(select(IdentitySession)
                         .where(IdentitySession.refresh_token_hash == _hash(payload.refresh_token))
                         .with_for_update())
    now = _now()
    if session is None or session.revoked_at or session.refresh_expires_at <= now:
        raise HTTPException(401, "Refresh token expired or revoked")
    user = db.get(IdentityUser, session.user_id)
    membership = db.scalar(select(Membership).where(
        Membership.user_id == session.user_id, Membership.organization_id == session.organization_id,
    ))
    organization = db.get(Organization, session.organization_id)
    if user is None or user.disabled or membership is None or organization is None:
        session.revoked_at = now
        db.commit()
        raise HTTPException(401, "Account or organization access revoked")
    session.revoked_at = now
    db.commit()
    return {**_user_view(user, organization, membership.role),
            **_issue_session(db, user, organization.id, session.device_name, settings)}


@router.post("/auth/logout")
def logout(principal: Principal = Depends(require_principal), db: Session = Depends(get_db)):
    principal.session.revoked_at = _now()
    db.commit()
    return {"signed_out": True}


@router.get("/auth/me")
def me(principal: Principal = Depends(require_principal), db: Session = Depends(get_db)):
    organization = db.get(Organization, principal.session.organization_id)
    return _user_view(principal.user, organization, principal.membership.role)


@router.get("/auth/sessions")
def list_sessions(principal: Principal = Depends(require_principal), db: Session = Depends(get_db)):
    rows = db.scalars(select(IdentitySession).where(
        IdentitySession.user_id == principal.user.id,
        IdentitySession.revoked_at.is_(None),
        IdentitySession.refresh_expires_at > _now(),
    ).order_by(IdentitySession.created_at.desc())).all()
    return [{"id": row.id, "device_name": row.device_name, "created_at": row.created_at,
             "last_used_at": row.last_used_at, "current": row.id == principal.session.id} for row in rows]


@router.delete("/auth/sessions/{session_id}")
def revoke_session(session_id: int, principal: Principal = Depends(require_principal), db: Session = Depends(get_db)):
    row = db.scalar(select(IdentitySession).where(
        IdentitySession.id == session_id, IdentitySession.user_id == principal.user.id,
    ))
    if row is None:
        raise HTTPException(404, "Session not found")
    row.revoked_at = _now()
    db.commit()
    return {"revoked": True}


@router.post("/auth/password-reset/request")
def request_password_reset(payload: EmailInput, request: Request, db: Session = Depends(get_db)):
    settings = IdentitySettings.load()
    if not settings.email_ready:
        raise HTTPException(503, "Identity email delivery is not configured")
    email = str(payload.email).strip().casefold()
    ip = _ip_key(request)
    _rate_limit(db, email, ip, settings, purpose="reset_request", include_success=True)
    user = db.scalar(select(IdentityUser).where(IdentityUser.email == email, IdentityUser.disabled.is_(False)))
    if user:
        code = _new_code()
        db.add(PasswordResetToken(user_id=user.id, token_hash=_hash(code),
                                  expires_at=_now() + timedelta(minutes=settings.email_code_minutes)))
        db.commit()
        _send_code(settings, user.email, "password reset", code)
    _record_attempt(db, email, ip, False, purpose="reset_request")
    return {"requested": True}


@router.post("/auth/password-reset/confirm")
def confirm_password_reset(payload: PasswordResetConfirm, request: Request, db: Session = Depends(get_db)):
    settings = IdentitySettings.load()
    email = str(payload.email).strip().casefold()
    ip = _ip_key(request)
    _rate_limit(db, email, ip, settings, purpose="reset_confirm")
    if not _EMAIL_CODE.fullmatch(payload.code):
        _record_attempt(db, email, ip, False, purpose="reset_confirm")
        raise HTTPException(400, "Invalid or expired reset code")
    user = db.scalar(select(IdentityUser).where(IdentityUser.email == email))
    token = db.scalar(select(PasswordResetToken).where(
        PasswordResetToken.user_id == user.id if user else False,
        PasswordResetToken.token_hash == _hash(payload.code),
        PasswordResetToken.used_at.is_(None),
        PasswordResetToken.expires_at > _now(),
    ))
    if user is None or token is None:
        _record_attempt(db, email, ip, False, purpose="reset_confirm")
        raise HTTPException(400, "Invalid or expired reset code")
    token.used_at = _now()
    user.password_hash = hash_password(payload.new_password)
    db.query(IdentitySession).filter(IdentitySession.user_id == user.id,
                                     IdentitySession.revoked_at.is_(None)).update({IdentitySession.revoked_at: _now()})
    db.commit()
    _record_attempt(db, email, ip, True, purpose="reset_confirm")
    return {"password_reset": True}


@router.get("/organizations")
def list_organizations(principal: Principal = Depends(require_principal), db: Session = Depends(get_db)):
    rows = db.execute(select(Membership, Organization).join(
        Organization, Organization.id == Membership.organization_id,
    ).where(Membership.user_id == principal.user.id)).all()
    return [{"id": org.id, "name": org.name, "edition": org.edition, "role": member.role,
             "active": org.id == principal.session.organization_id} for member, org in rows]


@router.post("/organizations")
def create_organization(payload: OrganizationInput, principal: Principal = Depends(require_principal), db: Session = Depends(get_db)):
    organization = Organization(name=payload.name.strip(), edition=payload.edition)
    db.add(organization)
    db.flush()
    db.add(Membership(organization_id=organization.id, user_id=principal.user.id, role="owner"))
    db.add(IdentityAuditEvent(actor_user_id=principal.user.id, organization_id=organization.id, action="organization.created"))
    db.commit()
    db.refresh(organization)
    return {"id": organization.id, "name": organization.name, "edition": organization.edition, "role": "owner"}


@router.post("/organizations/{organization_id}/switch")
def switch_organization(organization_id: int, principal: Principal = Depends(require_principal), db: Session = Depends(get_db)):
    membership = db.scalar(select(Membership).where(
        Membership.user_id == principal.user.id, Membership.organization_id == organization_id,
    ))
    if membership is None:
        raise HTTPException(404, "Organization not found")
    principal.session.revoked_at = _now()
    db.commit()
    organization = db.get(Organization, organization_id)
    return {**_user_view(principal.user, organization, membership.role),
            **_issue_session(db, principal.user, organization_id, principal.session.device_name,
                             IdentitySettings.load())}


@router.get("/organizations/{organization_id}/members")
def list_members(organization_id: int, principal: Principal = Depends(require_principal), db: Session = Depends(get_db)):
    if principal.session.organization_id != organization_id:
        raise HTTPException(404, "Organization not found")
    rows = db.scalars(select(Membership).where(Membership.organization_id == organization_id)).all()
    users = {user.id: user for user in db.scalars(select(IdentityUser).where(IdentityUser.id.in_([row.user_id for row in rows]))).all()}
    return [{"user_id": row.user_id, "email": users[row.user_id].email,
             "name": users[row.user_id].display_name, "role": row.role} for row in rows]


@router.get("/organizations/{organization_id}/audit")
def list_organization_audit(organization_id: int,
                            principal: Principal = Depends(require_roles("owner", "admin")),
                            db: Session = Depends(get_db)):
    if principal.session.organization_id != organization_id:
        raise HTTPException(404, "Organization not found")
    events = db.scalars(select(IdentityAuditEvent).where(
        IdentityAuditEvent.organization_id == organization_id,
    ).order_by(IdentityAuditEvent.id.desc()).limit(200)).all()
    return [{"id": event.id, "actor_user_id": event.actor_user_id,
             "action": event.action, "target_user_id": event.target_user_id,
             "created_at": event.created_at} for event in events]


@router.post("/organizations/{organization_id}/invitations")
def invite_member(organization_id: int, payload: InvitationInput, principal: Principal = Depends(require_roles("owner", "admin")), db: Session = Depends(get_db)):
    settings = IdentitySettings.load()
    if not settings.email_ready:
        raise HTTPException(503, "Identity email delivery is not configured")
    if principal.session.organization_id != organization_id:
        raise HTTPException(404, "Organization not found")
    email = str(payload.email).strip().casefold()
    existing = db.scalar(select(IdentityUser).where(IdentityUser.email == email))
    if existing and db.scalar(select(Membership).where(
        Membership.organization_id == organization_id, Membership.user_id == existing.id,
    )):
        raise HTTPException(409, "User is already a member")
    code = secrets.token_urlsafe(32)
    invitation = OrganizationInvitation(
        organization_id=organization_id, invited_email=email, role=payload.role,
        token_hash=_hash(code), created_by=principal.user.id, expires_at=_now() + timedelta(days=7),
    )
    db.add(invitation)
    db.add(IdentityAuditEvent(actor_user_id=principal.user.id, organization_id=organization_id,
                              action="organization.member_invited", target_user_id=existing.id if existing else None))
    db.commit()
    _send_code(settings, email, "organization invitation", code)
    return {"invited": True}


@router.post("/invitations/accept")
def accept_invitation(payload: AcceptInvitationInput, principal: Principal = Depends(require_principal), db: Session = Depends(get_db)):
    if not principal.user.email_verified:
        raise HTTPException(403, "Verify your email before accepting an invitation")
    invitation = db.scalar(select(OrganizationInvitation).where(
        OrganizationInvitation.token_hash == _hash(payload.code),
        OrganizationInvitation.accepted_at.is_(None), OrganizationInvitation.expires_at > _now(),
    ))
    if invitation is None or invitation.invited_email != principal.user.email:
        raise HTTPException(400, "Invitation is invalid or expired")
    existing = db.scalar(select(Membership).where(
        Membership.organization_id == invitation.organization_id, Membership.user_id == principal.user.id,
    ))
    if existing is None:
        db.add(Membership(organization_id=invitation.organization_id, user_id=principal.user.id, role=invitation.role))
    invitation.accepted_at = _now()
    db.add(IdentityAuditEvent(actor_user_id=principal.user.id, organization_id=invitation.organization_id,
                              action="organization.invitation_accepted", target_user_id=principal.user.id))
    db.commit()
    return {"accepted": True, "organization_id": invitation.organization_id}


@router.patch("/organizations/{organization_id}/members/{user_id}")
def change_member_role(organization_id: int, user_id: int, payload: RoleInput,
                       principal: Principal = Depends(require_roles("owner")), db: Session = Depends(get_db)):
    if principal.session.organization_id != organization_id:
        raise HTTPException(404, "Organization not found")
    membership = db.scalar(select(Membership).where(
        Membership.organization_id == organization_id, Membership.user_id == user_id,
    ))
    if membership is None or membership.role == "owner":
        raise HTTPException(404, "Member not found")
    membership.role = payload.role
    db.add(IdentityAuditEvent(actor_user_id=principal.user.id, organization_id=organization_id,
                              action="organization.member_role_changed", target_user_id=user_id))
    db.commit()
    return {"user_id": user_id, "role": membership.role}


@router.delete("/organizations/{organization_id}/members/{user_id}")
def remove_member(organization_id: int, user_id: int,
                  principal: Principal = Depends(require_roles("owner", "admin")), db: Session = Depends(get_db)):
    if principal.session.organization_id != organization_id or user_id == principal.user.id:
        raise HTTPException(404, "Member not found")
    membership = db.scalar(select(Membership).where(
        Membership.organization_id == organization_id, Membership.user_id == user_id,
    ))
    if membership is None or membership.role == "owner":
        raise HTTPException(404, "Member not found")
    if principal.membership.role == "admin" and membership.role == "admin":
        raise HTTPException(403, "Administrators cannot remove other administrators")
    db.delete(membership)
    db.add(IdentityAuditEvent(actor_user_id=principal.user.id, organization_id=organization_id,
                              action="organization.member_removed", target_user_id=user_id))
    db.commit()
    return {"removed": True}


@router.patch("/platform/users/{user_id}/status")
def set_account_status(user_id: int, payload: AccountStatusInput,
                       principal: Principal = Depends(require_platform_admin), db: Session = Depends(get_db)):
    user = db.get(IdentityUser, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    if principal.user.id == user_id and payload.disabled:
        raise HTTPException(400, "A platform administrator cannot disable their own account")
    user.disabled = payload.disabled
    if payload.disabled:
        db.query(IdentitySession).filter(
            IdentitySession.user_id == user_id, IdentitySession.revoked_at.is_(None),
        ).update({IdentitySession.revoked_at: _now()})
    db.add(IdentityAuditEvent(actor_user_id=principal.user.id, action="platform.account_status_changed",
                              target_user_id=user_id))
    db.commit()
    return {"user_id": user_id, "disabled": user.disabled}
