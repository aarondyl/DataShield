import os
from pathlib import Path

os.environ["IDENTITY_DATABASE_URL"] = "sqlite:////tmp/datashield-identity-service-test.db"
os.environ["IDENTITY_EMAIL_VERIFY_REQUIRED"] = "true"
os.environ["IDENTITY_SMTP_HOST"] = "smtp.test.invalid"
os.environ["IDENTITY_SMTP_USER"] = "datashield-test"
os.environ["IDENTITY_SMTP_PASSWORD_FILE"] = "/tmp/identity-test-password"
os.environ["IDENTITY_EMAIL_FROM"] = "accounts@datashield.test"
Path("/tmp/identity-test-password").write_text("test-only-password", encoding="utf-8")

from fastapi.testclient import TestClient
import pytest

from identity_service import api as identity_api
from identity_service.base import IdentityBase
from identity_service.database import engine, SessionLocal
from identity_service.models import IdentityAIUsage, IdentityUser
from identity_service.main import app


@pytest.fixture
def client(monkeypatch):
    IdentityBase.metadata.drop_all(engine)
    IdentityBase.metadata.create_all(engine)
    sent_codes = []
    monkeypatch.setattr(identity_api, "send_security_code",
                        lambda settings, email, purpose, code: sent_codes.append((email, purpose, code)))
    with TestClient(app) as test_client:
        yield test_client, sent_codes
    IdentityBase.metadata.drop_all(engine)


def _register_verified(client, codes, email="owner@example.test", org="Example Org"):
    result = client.post("/v1/auth/register", json={
        "email": email, "password": "correct horse battery staple 42", "name": "Owner",
        "organization_name": org, "edition": "enterprise",
    })
    assert result.status_code == 201, result.text
    assert result.json()["verification_required"] is True
    verify_code = codes[-1][2]
    verified = client.post("/v1/auth/verify-email", json={"email": email, "code": verify_code})
    assert verified.status_code == 200
    return email


def test_identity_registration_verification_login_refresh_revoke_and_password_reset(client):
    http, codes = client
    email = _register_verified(http, codes)
    login = http.post("/v1/auth/login", json={"email": email, "password": "correct horse battery staple 42"})
    assert login.status_code == 200
    first_tokens = login.json()
    assert first_tokens["organization"]["role"] == "owner"
    assert len(first_tokens["access_token"]) > 40

    refreshed = http.post("/v1/auth/refresh", json={"refresh_token": first_tokens["refresh_token"]})
    assert refreshed.status_code == 200
    second_tokens = refreshed.json()
    assert http.get("/v1/auth/me", headers={"Authorization": f"Bearer {first_tokens['access_token']}"}).status_code == 401
    assert http.get("/v1/auth/me", headers={"Authorization": f"Bearer {second_tokens['access_token']}"}).status_code == 200

    requested = http.post("/v1/auth/password-reset/request", json={"email": email})
    assert requested.status_code == 200 and requested.json() == {"requested": True}
    reset_code = codes[-1][2]
    reset = http.post("/v1/auth/password-reset/confirm", json={
        "email": email, "code": reset_code, "new_password": "a completely new password 89",
    })
    assert reset.status_code == 200
    assert http.post("/v1/auth/refresh", json={"refresh_token": second_tokens["refresh_token"]}).status_code == 401
    assert http.post("/v1/auth/login", json={"email": email, "password": "correct horse battery staple 42"}).status_code == 401
    assert http.post("/v1/auth/login", json={"email": email, "password": "a completely new password 89"}).status_code == 200


def test_identity_organization_switch_membership_and_rbac(client):
    http, codes = client
    owner_email = _register_verified(http, codes, org="Primary Org")
    owner_login = http.post("/v1/auth/login", json={"email": owner_email, "password": "correct horse battery staple 42"}).json()
    owner_headers = {"Authorization": f"Bearer {owner_login['access_token']}"}
    primary_id = owner_login["organization"]["id"]

    created_org = http.post("/v1/organizations", headers=owner_headers,
                            json={"name": "Second Org", "edition": "developer"})
    assert created_org.status_code == 200
    second_id = created_org.json()["id"]
    switched = http.post(f"/v1/organizations/{second_id}/switch", headers=owner_headers)
    assert switched.status_code == 200
    switched_tokens = switched.json()
    assert switched_tokens["organization"]["id"] == second_id
    assert http.get("/v1/organizations/{}/members".format(primary_id),
                    headers={"Authorization": f"Bearer {switched_tokens['access_token']}"}).status_code == 404

    invited_email = "member@example.test"
    invite = http.post(f"/v1/organizations/{second_id}/invitations", headers={
        "Authorization": f"Bearer {switched_tokens['access_token']}"},
        json={"email": invited_email, "role": "member"})
    assert invite.status_code == 200
    invite_code = codes[-1][2]

    _register_verified(http, codes, email=invited_email, org="Personal Org")
    member_login = http.post("/v1/auth/login", json={"email": invited_email,
                                                     "password": "correct horse battery staple 42"}).json()
    accepted = http.post("/v1/invitations/accept", headers={
        "Authorization": f"Bearer {member_login['access_token']}"}, json={"code": invite_code})
    assert accepted.status_code == 200
    members = http.get(f"/v1/organizations/{second_id}/members", headers={
        "Authorization": f"Bearer {switched_tokens['access_token']}"})
    assert {item["email"] for item in members.json()} == {owner_email, invited_email}
    audit = http.get(f"/v1/organizations/{second_id}/audit", headers={
        "Authorization": f"Bearer {switched_tokens['access_token']}"})
    assert audit.status_code == 200
    assert {item["action"] for item in audit.json()} >= {
        "organization.created", "organization.member_invited", "organization.invitation_accepted",
    }


def test_identity_authentication_is_rate_limited(client):
    http, _ = client
    for _ in range(8):
        assert http.post("/v1/auth/login", json={"email": "missing@example.test", "password": "incorrect"}).status_code == 401
    limited = http.post("/v1/auth/login", json={"email": "missing@example.test", "password": "incorrect"})
    assert limited.status_code == 429
    assert limited.headers["Retry-After"]


def test_platform_account_disable_requires_admin_and_revokes_sessions(client):
    http, codes = client
    email = _register_verified(http, codes)
    login = http.post("/v1/auth/login", json={"email": email,
                                             "password": "correct horse battery staple 42"}).json()
    target_email = _register_verified(http, codes, email="target@example.test", org="Target Org")
    target_login = http.post("/v1/auth/login", json={"email": target_email,
                                                    "password": "correct horse battery staple 42"}).json()
    with SessionLocal() as db:
        user = db.query(IdentityUser).filter_by(email=email).one()
        user.is_platform_admin = True
        db.commit()
        target_id = db.query(IdentityUser).filter_by(email=target_email).one().id
    admin_headers = {"Authorization": f"Bearer {login['access_token']}"}
    target_headers = {"Authorization": f"Bearer {target_login['access_token']}"}
    disabled = http.patch(f"/v1/platform/users/{target_id}/status", headers=admin_headers,
                          json={"disabled": True})
    assert disabled.status_code == 200 and disabled.json()["disabled"] is True
    assert http.get("/v1/auth/me", headers=target_headers).status_code == 401
    assert http.post("/v1/auth/login", json={"email": target_email,
                                              "password": "correct horse battery staple 42"}).status_code == 401


def test_cloud_ai_gateway_requires_account_and_validates_json(monkeypatch, client, tmp_path):
    http, codes = client
    email = _register_verified(http, codes)
    tokens = http.post("/v1/auth/login", json={"email": email,
        "password": "correct horse battery staple 42"}).json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    key_path = tmp_path / "platform-key"
    key_path.write_text("test-only-deepseek-key", encoding="utf-8")
    monkeypatch.setenv("IDENTITY_LLM_API_KEY_FILE", str(key_path))
    requests = []

    class Response:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {"choices": [{"message": {"content": '{"ok":true}'}}]}

    class AsyncClient:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, url, **kwargs):
            requests.append((url, kwargs))
            return Response()

    monkeypatch.setattr(identity_api.httpx, "AsyncClient", AsyncClient)
    payload = {"system_prompt": "Return JSON", "user_prompt": "Check"}
    assert http.post("/v1/ai/chat-json", json=payload).status_code == 401
    result = http.post("/v1/ai/chat-json", headers=headers, json=payload)
    assert result.status_code == 200 and result.json()["result"] == {"ok": True}
    assert result.json()["usage"] == {"input_tokens": 0, "output_tokens": 0}
    assert requests[0][0] == "https://api.deepseek.com/chat/completions"
    assert requests[0][1]["headers"]["Authorization"] == "Bearer test-only-deepseek-key"
    assert requests[0][1]["json"]["model"] == "deepseek-flash"
    with SessionLocal() as db:
        usage = db.query(IdentityAIUsage).one()
        assert usage.user_id > 0 and usage.status == "SUCCEEDED"
        assert not hasattr(usage, "prompt") and not hasattr(usage, "user_prompt")
    for _ in range(11):
        assert http.post("/v1/ai/chat-json", headers=headers, json=payload).status_code == 200
    limited = http.post("/v1/ai/chat-json", headers=headers, json=payload)
    assert limited.status_code == 429 and limited.headers["Retry-After"] == "60"
    assert len(requests) == 12
