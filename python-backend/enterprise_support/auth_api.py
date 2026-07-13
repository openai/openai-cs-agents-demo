from __future__ import annotations

import base64
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from .identity import AuthSettings, _identity_from_oidc


router = APIRouter(prefix="/auth", tags=["authentication"])


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise HTTPException(status_code=503, detail=f"{name} is not configured")
    return value


def _safe_return_to(value: str | None) -> str:
    if not value or not value.startswith("/") or value.startswith("//"):
        return "/support"
    return value[:500]


def _flow_cookie(payload: dict) -> str:
    return jwt.encode(
        {
            **payload,
            "type": "oidc_flow",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=10),
            "iss": "enterprise-ai-support-agent",
            "aud": "enterprise-agent-oidc-flow",
        },
        _required("SESSION_SIGNING_KEY"),
        algorithm="HS256",
    )


def _decode_flow(token: str) -> dict:
    try:
        claims = jwt.decode(
            token,
            _required("SESSION_SIGNING_KEY"),
            algorithms=["HS256"],
            issuer="enterprise-ai-support-agent",
            audience="enterprise-agent-oidc-flow",
        )
    except Exception as exc:
        raise HTTPException(status_code=401, detail="OIDC flow has expired or is invalid") from exc
    if claims.get("type") != "oidc_flow":
        raise HTTPException(status_code=401, detail="Invalid OIDC flow")
    return claims


@router.get("/login")
async def login(return_to: str | None = Query(default=None)) -> RedirectResponse:
    if os.getenv("AUTH_MODE", "dev") != "oidc":
        raise HTTPException(status_code=404, detail="OIDC login is disabled")
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    redirect_uri = _required("OIDC_REDIRECT_URI")
    parameters = {
        "response_type": "code",
        "client_id": _required("OIDC_CLIENT_ID"),
        "redirect_uri": redirect_uri,
        "scope": os.getenv("OIDC_SCOPES", "openid profile email"),
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    response = RedirectResponse(
        f"{_required('OIDC_AUTHORIZATION_ENDPOINT')}?{urlencode(parameters)}",
        status_code=302,
    )
    response.set_cookie(
        "oidc_flow",
        _flow_cookie(
            {
                "state": state,
                "nonce": nonce,
                "verifier": verifier,
                "return_to": _safe_return_to(return_to),
            }
        ),
        max_age=600,
        httponly=True,
        secure=os.getenv("APP_ENV") == "production",
        samesite="lax",
        path="/auth",
    )
    return response


@router.get("/callback")
async def callback(
    request: Request,
    code: str,
    state: str,
) -> RedirectResponse:
    flow_token = request.cookies.get("oidc_flow")
    if not flow_token:
        raise HTTPException(status_code=401, detail="OIDC flow cookie is missing")
    flow = _decode_flow(flow_token)
    if not secrets.compare_digest(str(flow.get("state", "")), state):
        raise HTTPException(status_code=401, detail="OIDC state validation failed")
    async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
        token_response = await client.post(
            _required("OIDC_TOKEN_ENDPOINT"),
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": _required("OIDC_REDIRECT_URI"),
                "client_id": _required("OIDC_CLIENT_ID"),
                "client_secret": os.getenv("OIDC_CLIENT_SECRET", ""),
                "code_verifier": flow["verifier"],
            },
            headers={"Accept": "application/json"},
        )
    if token_response.status_code >= 400:
        raise HTTPException(status_code=401, detail="OIDC token exchange failed")
    token_payload = token_response.json()
    id_token = token_payload.get("id_token")
    if not id_token:
        raise HTTPException(status_code=401, detail="OIDC provider did not return an ID token")
    identity = _identity_from_oidc(
        str(id_token),
        AuthSettings.from_env(),
        expected_nonce=str(flow["nonce"]),
    )
    session_token = jwt.encode(
        {
            "type": "user_session",
            "sub": identity.user_id,
            "tenant_id": identity.tenant_id,
            "roles": sorted(identity.roles),
            "jti": secrets.token_urlsafe(24),
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(hours=int(os.getenv("SESSION_TTL_HOURS", "8"))),
            "iss": "enterprise-ai-support-agent",
            "aud": "enterprise-agent-session",
        },
        _required("SESSION_SIGNING_KEY"),
        algorithm="HS256",
    )
    frontend_url = os.getenv("FRONTEND_BASE_URL", "http://localhost:3000").rstrip("/")
    response = RedirectResponse(f"{frontend_url}{_safe_return_to(flow.get('return_to'))}", status_code=302)
    response.delete_cookie("oidc_flow", path="/auth")
    response.set_cookie(
        "enterprise_session",
        session_token,
        max_age=int(os.getenv("SESSION_TTL_HOURS", "8")) * 3600,
        httponly=True,
        secure=os.getenv("APP_ENV") == "production",
        samesite="lax",
        path="/",
    )
    return response


def _logout_response(return_to: str | None = None) -> RedirectResponse:
    frontend_url = os.getenv("FRONTEND_BASE_URL", "http://localhost:3000").rstrip("/")
    redirect_target = frontend_url
    if return_to:
        redirect_target = f"{frontend_url}{_safe_return_to(return_to)}"
    response = RedirectResponse(redirect_target, status_code=303)
    response.delete_cookie("enterprise_session", path="/")
    return response


@router.post("/logout")
async def logout(return_to: str | None = Query(default=None)) -> RedirectResponse:
    return _logout_response(return_to)


@router.get("/logout")
async def logout_get(return_to: str | None = Query(default=None)) -> RedirectResponse:
    return _logout_response(return_to)
