import pytest
from fastapi import HTTPException

from enterprise_support.identity import (
    AuthSettings,
    RequestIdentity,
    _identity_from_oidc,
    _identity_from_session,
    as_portal_identity,
    get_request_identity,
)


@pytest.mark.asyncio
async def test_development_identity_comes_from_server_configuration(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_MODE", "dev")
    monkeypatch.setenv("DEV_AUTH_TOKEN", "test-token")
    monkeypatch.setenv("DEV_TENANT_ID", "tenant-a")
    monkeypatch.setenv("DEV_USER_ID", "user-a")
    monkeypatch.setenv("DEV_USER_ROLES", "tenant_admin,end_user")

    identity = await get_request_identity("Bearer test-token")

    assert identity.tenant_id == "tenant-a"
    assert identity.user_id == "user-a"
    assert identity.roles == frozenset({"tenant_admin", "end_user"})


@pytest.mark.asyncio
async def test_development_identity_rejects_invalid_token(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_MODE", "dev")
    monkeypatch.setenv("DEV_AUTH_TOKEN", "test-token")

    with pytest.raises(HTTPException) as exc_info:
        await get_request_identity("Bearer wrong-token")

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_roboage_identity_uses_signed_service_headers(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_MODE", "roboage")
    monkeypatch.setenv("ROBOAGE_INTERNAL_TOKEN", "service-token")

    identity = await get_request_identity(
        "Bearer service-token",
        x_roboage_tenant_id="enterprise-1",
        x_roboage_user_id="user-1",
        x_roboage_roles="tenant_admin,support_agent,unknown_role",
    )

    assert identity.tenant_id == "enterprise-1"
    assert identity.user_id == "user-1"
    assert identity.roles == frozenset({"tenant_admin", "support_agent"})


@pytest.mark.asyncio
async def test_roboage_identity_rejects_invalid_service_token(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_MODE", "roboage")
    monkeypatch.setenv("ROBOAGE_INTERNAL_TOKEN", "service-token")

    with pytest.raises(HTTPException) as exc_info:
        await get_request_identity(
            "Bearer wrong-token",
            x_roboage_tenant_id="enterprise-1",
            x_roboage_user_id="user-1",
            x_roboage_roles="tenant_admin",
        )

    assert exc_info.value.status_code == 401


def test_portal_identity_drops_administrative_roles() -> None:
    identity = RequestIdentity(
        tenant_id="tenant-a",
        user_id="admin-a",
        roles=frozenset({"tenant_admin", "support_agent", "legal_reader"}),
    )

    portal_identity = as_portal_identity(identity)

    assert portal_identity.tenant_id == identity.tenant_id
    assert portal_identity.user_id == identity.user_id
    assert portal_identity.roles == frozenset({"end_user", "legal_reader"})


def test_oidc_groups_map_to_allowed_roles(monkeypatch) -> None:
    monkeypatch.setenv("OIDC_GROUP_ROLE_MAPPING", '{"support-team":["support_agent","not-a-role"]}')
    settings = AuthSettings.from_env()

    class SigningKey:
        key = "public-key"

    class JWKClient:
        def __init__(self, url):
            pass

        def get_signing_key_from_jwt(self, token):
            return SigningKey()

    monkeypatch.setattr("enterprise_support.identity.PyJWKClient", JWKClient)
    monkeypatch.setattr(
        "enterprise_support.identity.jwt.decode",
        lambda *args, **kwargs: {
            "tenant_id": "tenant-a",
            "sub": "user-a",
            "roles": ["end_user", "unknown-role"],
            "groups": ["support-team"],
        },
    )
    settings = settings.__class__(
        **{
            **settings.__dict__,
            "oidc_issuer": "https://issuer.example.com",
            "oidc_audience": "audience",
            "oidc_jwks_url": "https://issuer.example.com/jwks",
        }
    )

    identity = _identity_from_oidc("jwt", settings)

    assert identity.roles == frozenset({"end_user", "support_agent"})


def test_http_only_session_identity_uses_signed_claims(monkeypatch) -> None:
    import jwt

    monkeypatch.setenv("SESSION_SIGNING_KEY", "test-session-signing-key-with-sufficient-length")
    token = jwt.encode(
        {
            "type": "user_session",
            "sub": "user-a",
            "tenant_id": "tenant-a",
            "roles": ["support_agent", "invalid-role"],
            "iss": "enterprise-ai-support-agent",
            "aud": "enterprise-agent-session",
        },
        "test-session-signing-key-with-sufficient-length",
        algorithm="HS256",
    )

    identity = _identity_from_session(token)

    assert identity.tenant_id == "tenant-a"
    assert identity.roles == frozenset({"support_agent"})
