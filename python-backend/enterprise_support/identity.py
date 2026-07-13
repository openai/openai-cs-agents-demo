from __future__ import annotations

import os
import json
import secrets
from dataclasses import dataclass
from typing import Annotated, Callable

import jwt
from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from jwt import PyJWKClient
from pydantic import BaseModel, Field


ADMINISTRATIVE_ROLES = frozenset(
    {"tenant_admin", "knowledge_editor", "knowledge_reviewer", "support_agent"}
)
ALLOWED_ROLES = ADMINISTRATIVE_ROLES.union({"end_user", "legal_reader", "billing_reader"})


class RequestIdentity(BaseModel):
    tenant_id: str
    user_id: str
    roles: frozenset[str] = Field(default_factory=frozenset)

    def has_any_role(self, *roles: str) -> bool:
        return bool(self.roles.intersection(roles))


@dataclass(frozen=True)
class AuthSettings:
    mode: str
    dev_token: str
    dev_tenant_id: str
    dev_user_id: str
    dev_user_roles: tuple[str, ...]
    oidc_issuer: str | None
    oidc_audience: str | None
    oidc_jwks_url: str | None
    oidc_roles_claim: str
    oidc_groups_claim: str
    oidc_group_role_mapping: dict[str, tuple[str, ...]]

    @classmethod
    def from_env(cls) -> "AuthSettings":
        roles = tuple(
            role.strip()
            for role in os.getenv(
                "DEV_USER_ROLES",
                "tenant_admin,knowledge_editor,knowledge_reviewer,support_agent,end_user",
            ).split(",")
            if role.strip()
        )
        try:
            raw_mapping = json.loads(os.getenv("OIDC_GROUP_ROLE_MAPPING", "{}"))
        except json.JSONDecodeError as exc:
            raise RuntimeError("OIDC_GROUP_ROLE_MAPPING must be valid JSON") from exc
        if not isinstance(raw_mapping, dict):
            raise RuntimeError("OIDC_GROUP_ROLE_MAPPING must be a JSON object")
        mapping = {
            str(group): tuple(str(role) for role in mapped_roles if str(role) in ALLOWED_ROLES)
            for group, mapped_roles in raw_mapping.items()
            if isinstance(mapped_roles, list)
        }
        return cls(
            mode=os.getenv("AUTH_MODE", "dev").strip().lower(),
            dev_token=os.getenv("DEV_AUTH_TOKEN", "local-dev-token"),
            dev_tenant_id=os.getenv("DEV_TENANT_ID", "tenant_acme_cn"),
            dev_user_id=os.getenv("DEV_USER_ID", "local-admin"),
            dev_user_roles=roles,
            oidc_issuer=os.getenv("OIDC_ISSUER") or None,
            oidc_audience=os.getenv("OIDC_AUDIENCE") or None,
            oidc_jwks_url=os.getenv("OIDC_JWKS_URL") or None,
            oidc_roles_claim=os.getenv("OIDC_ROLES_CLAIM", "roles"),
            oidc_groups_claim=os.getenv("OIDC_GROUPS_CLAIM", "groups"),
            oidc_group_role_mapping=mapping,
        )


def _unauthorized(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=message,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise _unauthorized("Missing bearer token")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise _unauthorized("Invalid authorization header")
    return token


def _identity_from_oidc(
    token: str,
    settings: AuthSettings,
    *,
    expected_nonce: str | None = None,
) -> RequestIdentity:
    if not settings.oidc_jwks_url or not settings.oidc_issuer or not settings.oidc_audience:
        raise RuntimeError(
            "OIDC_JWKS_URL, OIDC_ISSUER, and OIDC_AUDIENCE are required in oidc mode"
        )
    try:
        signing_key = PyJWKClient(settings.oidc_jwks_url).get_signing_key_from_jwt(
            token
        )
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256", "ES256"],
            audience=settings.oidc_audience,
            issuer=settings.oidc_issuer,
        )
    except Exception as exc:
        raise _unauthorized("Token validation failed") from exc

    if expected_nonce is not None and not secrets.compare_digest(
        str(claims.get("nonce", "")), expected_nonce
    ):
        raise _unauthorized("OIDC nonce validation failed")

    tenant_id = claims.get("tenant_id")
    user_id = claims.get("sub")
    raw_roles = claims.get(settings.oidc_roles_claim, [])
    roles = raw_roles.split() if isinstance(raw_roles, str) else raw_roles
    raw_groups = claims.get(settings.oidc_groups_claim, [])
    groups = raw_groups.split() if isinstance(raw_groups, str) else raw_groups
    if not tenant_id or not user_id or not isinstance(roles, list):
        raise _unauthorized("Token is missing tenant or role claims")
    mapped_roles = set(str(role) for role in roles if str(role) in ALLOWED_ROLES)
    if isinstance(groups, list):
        for group in groups:
            mapped_roles.update(settings.oidc_group_role_mapping.get(str(group), ()))
    return RequestIdentity(
        tenant_id=str(tenant_id),
        user_id=str(user_id),
        roles=frozenset(mapped_roles),
    )


def _identity_from_session(token: str) -> RequestIdentity:
    signing_key = os.getenv("SESSION_SIGNING_KEY")
    if not signing_key:
        raise _unauthorized("Session authentication is not configured")
    try:
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["HS256"],
            audience="enterprise-agent-session",
            issuer="enterprise-ai-support-agent",
        )
    except Exception as exc:
        raise _unauthorized("Session validation failed") from exc
    if claims.get("type") != "user_session":
        raise _unauthorized("Invalid session type")
    tenant_id = claims.get("tenant_id")
    user_id = claims.get("sub")
    roles = claims.get("roles", [])
    if not tenant_id or not user_id or not isinstance(roles, list):
        raise _unauthorized("Session is missing identity claims")
    return RequestIdentity(
        tenant_id=str(tenant_id),
        user_id=str(user_id),
        roles=frozenset(str(role) for role in roles if str(role) in ALLOWED_ROLES),
    )


async def get_request_identity(
    authorization: Annotated[str | None, Header()] = None,
    request: Request = None,
    enterprise_session: Annotated[str | None, Cookie()] = None,
    x_roboage_tenant_id: Annotated[
        str | None, Header(alias="X-RoboAge-Tenant-Id")
    ] = None,
    x_roboage_user_id: Annotated[
        str | None, Header(alias="X-RoboAge-User-Id")
    ] = None,
    x_roboage_roles: Annotated[
        str | None, Header(alias="X-RoboAge-Roles")
    ] = None,
) -> RequestIdentity:
    settings = AuthSettings.from_env()
    if settings.mode == "roboage":
        token = _bearer_token(authorization)
        expected_token = os.getenv("ROBOAGE_INTERNAL_TOKEN") or settings.dev_token
        if not expected_token:
            raise RuntimeError("ROBOAGE_INTERNAL_TOKEN is required in roboage mode")
        if not secrets.compare_digest(token, expected_token):
            raise _unauthorized("Invalid RoboAge service token")
        if not x_roboage_tenant_id or not x_roboage_user_id:
            raise _unauthorized("Missing RoboAge tenant or user headers")
        roles = frozenset(
            role.strip()
            for role in (x_roboage_roles or "").split(",")
            if role.strip() in ALLOWED_ROLES
        )
        return RequestIdentity(
            tenant_id=x_roboage_tenant_id,
            user_id=x_roboage_user_id,
            roles=roles,
        )
    if settings.mode == "dev":
        token = _bearer_token(authorization)
        if token != settings.dev_token:
            raise _unauthorized("Invalid development token")
        return RequestIdentity(
            tenant_id=settings.dev_tenant_id,
            user_id=settings.dev_user_id,
            roles=frozenset(settings.dev_user_roles),
        )
    if settings.mode == "oidc":
        identity = (
            _identity_from_oidc(_bearer_token(authorization), settings)
            if authorization
            else _identity_from_session(enterprise_session or "")
        )
        store = getattr(getattr(request, "app", None), "state", None) if request else None
        persistent_store = getattr(store, "store", None) if store else None
        if persistent_store is not None and hasattr(persistent_store, "authorize_identity"):
            try:
                return persistent_store.authorize_identity(identity)
            except PermissionError as exc:
                raise _unauthorized(str(exc)) from exc
        return identity
    raise RuntimeError(f"Unsupported AUTH_MODE: {settings.mode}")


def require_roles(*allowed_roles: str) -> Callable:
    async def dependency(
        identity: Annotated[RequestIdentity, Depends(get_request_identity)],
    ) -> RequestIdentity:
        if not identity.has_any_role(*allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return identity

    return dependency


def identity_from_context(context: dict) -> RequestIdentity:
    identity = context.get("identity")
    if isinstance(identity, RequestIdentity):
        return identity
    if isinstance(identity, dict):
        return RequestIdentity.model_validate(identity)
    raise PermissionError("Authenticated identity is required")


def as_portal_identity(identity: RequestIdentity) -> RequestIdentity:
    roles = set(identity.roles).difference(ADMINISTRATIVE_ROLES)
    roles.add("end_user")
    return identity.model_copy(update={"roles": frozenset(roles)})
