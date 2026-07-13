from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from chatkit.types import ThreadMetadata
from fastapi.testclient import TestClient

import main
from enterprise_support.identity import RequestIdentity
from enterprise_support.production import production_readiness_checks
from persistent_store import PersistentStore
from server import EnterpriseSupportServer


def test_health_reports_zhipu_provider(monkeypatch) -> None:
    monkeypatch.setattr(
        main,
        "ZAI_SETTINGS",
        SimpleNamespace(configured=True, agent_model="glm-test"),
    )

    response = TestClient(main.app).get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "enterprise-ai-support-agent",
        "model_provider": "zhipu",
        "model": "glm-test",
        "configured": True,
    }


def test_chat_endpoint_rejects_missing_zai_key(monkeypatch) -> None:
    monkeypatch.setattr(
        main,
        "ZAI_SETTINGS",
        SimpleNamespace(configured=False, agent_model="glm-test"),
    )
    monkeypatch.setenv("AUTH_MODE", "dev")

    response = TestClient(main.app).post(
        "/chatkit",
        content=b"{}",
        headers={"Authorization": "Bearer local-dev-token"},
    )

    assert response.status_code == 503
    assert response.json()["error"] == "model_provider_not_configured"


def test_chat_endpoint_requires_authentication(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_MODE", "dev")
    response = TestClient(main.app).post("/chatkit", content=b"{}")

    assert response.status_code == 401


def test_roboage_chat_endpoint_uses_roboage_identity_and_json_contract(monkeypatch) -> None:
    monkeypatch.setattr(
        main,
        "ZAI_SETTINGS",
        SimpleNamespace(configured=True, agent_model="glm-test"),
    )
    monkeypatch.setenv("AUTH_MODE", "roboage")
    monkeypatch.setenv("ROBOAGE_INTERNAL_TOKEN", "service-token")

    class CapturingServer:
        def __init__(self) -> None:
            self.calls = []

        async def respond_json(self, **kwargs):
            self.calls.append(kwargs)
            return {
                "answer": "企业版 SLA 为 99.9%。",
                "thread_id": "thread-1",
                "citations": [{"source": "sla.pdf"}],
            }

    server = CapturingServer()
    main.app.dependency_overrides[main.get_server] = lambda: server
    client = TestClient(main.app)

    try:
        response = client.post(
            "/v1/roboage/chat",
            json={
                "message": "企业版 SLA 是什么？",
                "history": [{"role": "user", "content": "上一轮问题"}],
                "thread_id": "thread-1",
            },
            headers={
                "Authorization": "Bearer service-token",
                "X-RoboAge-Tenant-Id": "enterprise-1",
                "X-RoboAge-User-Id": "user-1",
                "X-RoboAge-Roles": "tenant_admin,support_agent",
            },
        )

        assert response.status_code == 200
        assert response.json()["answer"] == "企业版 SLA 为 99.9%。"
        assert response.json()["thread_id"] == "thread-1"
        call = server.calls[0]
        assert call["message"] == "企业版 SLA 是什么？"
        assert call["thread_id"] == "thread-1"
        assert call["history"] == [{"role": "user", "content": "上一轮问题"}]
        assert call["context"]["identity"].tenant_id == "enterprise-1"
        assert call["context"]["identity"].user_id == "user-1"
        assert call["context"]["include_runner_events"] is False
    finally:
        main.app.dependency_overrides.clear()


def test_roboage_chat_endpoint_rejects_missing_model_provider(monkeypatch) -> None:
    monkeypatch.setattr(
        main,
        "ZAI_SETTINGS",
        SimpleNamespace(configured=False, agent_model="glm-test"),
    )
    monkeypatch.setenv("AUTH_MODE", "roboage")
    monkeypatch.setenv("ROBOAGE_INTERNAL_TOKEN", "service-token")

    response = TestClient(main.app).post(
        "/v1/roboage/chat",
        json={"message": "企业版 SLA 是什么？"},
        headers={
            "Authorization": "Bearer service-token",
            "X-RoboAge-Tenant-Id": "enterprise-1",
            "X-RoboAge-User-Id": "user-1",
            "X-RoboAge-Roles": "tenant_admin,support_agent",
        },
    )

    assert response.status_code == 503
    assert response.json()["error"] == "model_provider_not_configured"


def test_oidc_login_uses_pkce_and_http_only_flow_cookie(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_MODE", "oidc")
    monkeypatch.setenv("SESSION_SIGNING_KEY", "test-session-signing-key-with-sufficient-length")
    monkeypatch.setenv("OIDC_AUTHORIZATION_ENDPOINT", "https://idp.example.com/authorize")
    monkeypatch.setenv("OIDC_CLIENT_ID", "client-id")
    monkeypatch.setenv("OIDC_REDIRECT_URI", "http://localhost:8000/auth/callback")

    response = TestClient(main.app).get(
        "/auth/login?return_to=/admin/quality",
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"].startswith("https://idp.example.com/authorize?")
    assert "code_challenge_method=S256" in response.headers["location"]
    assert "oidc_flow=" in response.headers["set-cookie"]
    assert "HttpOnly" in response.headers["set-cookie"]


def test_chat_endpoint_separates_portal_and_admin_surfaces(monkeypatch) -> None:
    monkeypatch.setattr(
        main,
        "ZAI_SETTINGS",
        SimpleNamespace(configured=True, agent_model="glm-test"),
    )
    monkeypatch.setenv(
        "DEV_USER_ROLES",
        "tenant_admin,support_agent,knowledge_editor,end_user",
    )
    monkeypatch.setenv("AUTH_MODE", "dev")

    class CapturingServer:
        def __init__(self) -> None:
            self.contexts = []

        async def process(self, payload, context):
            self.contexts.append(context)
            return SimpleNamespace(json="{}")

    server = CapturingServer()
    main.app.dependency_overrides[main.get_server] = lambda: server
    client = TestClient(main.app)

    try:
        portal_response = client.post(
            "/chatkit",
            content=b"{}",
            headers={
                "Authorization": "Bearer local-dev-token",
                "X-Client-Surface": "portal",
            },
        )
        admin_response = client.post(
            "/chatkit",
            content=b"{}",
            headers={
                "Authorization": "Bearer local-dev-token",
                "X-Client-Surface": "admin",
            },
        )

        assert portal_response.status_code == 200
        assert admin_response.status_code == 200
        assert server.contexts[0]["client_surface"] == "portal"
        assert server.contexts[0]["include_runner_events"] is False
        assert "tenant_admin" not in server.contexts[0]["identity"].roles
        assert server.contexts[1]["client_surface"] == "admin"
        assert server.contexts[1]["include_runner_events"] is True
        assert "tenant_admin" in server.contexts[1]["identity"].roles
    finally:
        main.app.dependency_overrides.clear()


def test_runner_state_endpoints_require_operator_role(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_MODE", "dev")
    monkeypatch.setenv("DEV_USER_ROLES", "end_user")

    response = TestClient(main.app).get(
        "/chatkit/bootstrap",
        headers={"Authorization": "Bearer local-dev-token"},
    )

    assert response.status_code == 403


def test_production_readiness_allows_roboage_server_to_server_mode(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("AUTH_MODE", "roboage")
    monkeypatch.setenv("ROBOAGE_INTERNAL_TOKEN", "service-token")
    monkeypatch.setenv("DATABASE_URL", "postgresql://agent:secret@postgres:5432/agent")
    monkeypatch.setenv("DATA_ENCRYPTION_KEY", "fernet-key")
    monkeypatch.setenv("CONNECTOR_MODE", "live")
    monkeypatch.setenv("DOCUMENT_PROCESSING_MODE", "async")
    monkeypatch.setenv("OBJECT_STORAGE_BACKEND", "s3")
    monkeypatch.setenv("S3_BUCKET", "enterprise-agent")
    monkeypatch.setenv("CLAMAV_COMMAND", "clamscan")
    monkeypatch.setenv("OPENAI_TRACING_DISABLED", "1")
    monkeypatch.setenv("CORS_ORIGINS", "https://www.roboage.net")

    checks = production_readiness_checks()

    assert {check.name for check in checks} >= {"auth_mode", "roboage_service_token"}
    assert "oidc_configuration" not in {check.name for check in checks}
    assert all(check.passed for check in checks)


@pytest.mark.asyncio
async def test_bootstrap_restores_latest_authorized_thread() -> None:
    store = PersistentStore(":memory:")
    server = EnterpriseSupportServer(store=store)
    identity = RequestIdentity(
        tenant_id="tenant-a",
        user_id="user-a",
        roles=frozenset({"end_user"}),
    )
    context = {"identity": identity}
    older = ThreadMetadata(id="thr_older", created_at=datetime.now() - timedelta(days=1))
    latest = ThreadMetadata(id="thr_latest", created_at=datetime.now())
    await store.save_thread(older, context)
    await store.save_thread(latest, context)

    result = await main.chatkit_bootstrap(identity, server)

    assert result["thread_id"] == latest.id
    store.close()
