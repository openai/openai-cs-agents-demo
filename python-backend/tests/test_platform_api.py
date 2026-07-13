from fastapi.testclient import TestClient

import main
from persistent_store import PersistentStore


AUTH_HEADERS = {"Authorization": "Bearer local-dev-token"}


def test_knowledge_document_lifecycle_and_gap_safe_search() -> None:
    original_store = main.app.state.store
    store = PersistentStore(":memory:")
    main.app.state.store = store
    client = TestClient(main.app)

    try:
        unauthorized = client.get("/v1/knowledge/documents")
        assert unauthorized.status_code == 401

        created = client.post(
            "/v1/knowledge/documents",
            headers=AUTH_HEADERS,
            json={
                "title": "DeepSeek 企业售后政策",
                "content": "企业客户可通过专属工单渠道获得技术支持。",
                "category": "product",
            },
        )
        assert created.status_code == 201
        document = created.json()
        assert document["status"] == "draft"

        before_publish = client.post(
            "/v1/knowledge/search/test",
            headers=AUTH_HEADERS,
            json={"query": "DeepSeek 售后服务政策"},
        ).json()
        assert before_publish["status"] == "insufficient_evidence"

        published = client.post(
            f"/v1/knowledge/documents/{document['id']}/publish",
            headers=AUTH_HEADERS,
        )
        assert published.status_code == 200

        after_publish = client.post(
            "/v1/knowledge/search/test",
            headers=AUTH_HEADERS,
            json={"query": "DeepSeek 售后服务政策"},
        ).json()
        assert after_publish["status"] == "grounded"
        assert after_publish["results"][0]["document_id"] == document["id"]

        unknown = client.post(
            "/v1/knowledge/search/test",
            headers=AUTH_HEADERS,
            json={"query": "火星基地完全未知产品"},
        ).json()
        assert unknown == {
            "status": "insufficient_evidence",
            "results": [],
            "knowledge_gap": True,
        }
    finally:
        main.app.state.store = original_store
        store.close()


def test_branding_is_tenant_scoped_and_portal_safe(monkeypatch) -> None:
    original_store = main.app.state.store
    store = PersistentStore(":memory:")
    main.app.state.store = store
    client = TestClient(main.app)

    try:
        monkeypatch.setenv("DEV_TENANT_ID", "tenant-brand-a")
        monkeypatch.setenv("DEV_USER_ID", "admin-a")
        monkeypatch.setenv("DEV_USER_ROLES", "tenant_admin")
        updated = client.patch(
            "/v1/admin/settings/branding",
            headers=AUTH_HEADERS,
            json={
                "display_name": "星河智能",
                "assistant_name": "星河服务助手",
                "logo_url": None,
                "primary_color": "#146c5a",
                "welcome_message": "您好，请问需要什么帮助？",
                "support_notice": "回答基于星河智能已审核资料。",
                "suggested_prompts": [
                    {"label": "产品咨询", "prompt": "请介绍企业版产品。"}
                ],
            },
        )
        assert updated.status_code == 200
        assert updated.json()["display_name"] == "星河智能"

        portal = client.get("/v1/portal/config", headers=AUTH_HEADERS)
        assert portal.status_code == 200
        assert portal.json()["branding"]["display_name"] == "星河智能"
        assert portal.json()["service"]["status"] in {"online", "offline"}
        assert "tenant_id" not in portal.json()["branding"]
        assert "updated_by" not in portal.json()["branding"]

        monkeypatch.setenv("DEV_TENANT_ID", "tenant-brand-b")
        second_tenant = client.get("/v1/portal/config", headers=AUTH_HEADERS)
        assert second_tenant.status_code == 200
        assert second_tenant.json()["branding"]["display_name"] != "星河智能"

        monkeypatch.setenv("DEV_USER_ROLES", "end_user")
        forbidden = client.get(
            "/v1/admin/settings/branding", headers=AUTH_HEADERS
        )
        assert forbidden.status_code == 403
    finally:
        main.app.state.store = original_store
        store.close()


def test_portal_threads_require_authentication() -> None:
    response = TestClient(main.app).get("/v1/portal/threads")

    assert response.status_code == 401


def test_quality_summary_does_not_report_development_as_production_ready(monkeypatch) -> None:
    original_store = main.app.state.store
    store = PersistentStore(":memory:")
    main.app.state.store = store
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DEV_USER_ROLES", "tenant_admin")

    try:
        response = TestClient(main.app).get(
            "/v1/admin/quality/summary",
            headers=AUTH_HEADERS,
        )

        assert response.status_code == 200
        assert response.json()["readiness"]["status"] == "development"
    finally:
        main.app.state.store = original_store
        store.close()


def test_connector_api_rejects_write_scopes_and_inline_secrets(monkeypatch) -> None:
    original_store = main.app.state.store
    store = PersistentStore(":memory:")
    main.app.state.store = store
    client = TestClient(main.app)
    monkeypatch.setenv("DEV_USER_ROLES", "tenant_admin")

    base = {
        "connector_type": "crm",
        "provider": "hubspot",
        "environment": "sandbox",
        "status": "enabled",
        "credential_reference": "env://HUBSPOT_ACCESS_TOKEN",
        "granted_scopes": ["crm.objects.companies.read"],
        "settings": {"company_id": "123"},
    }
    try:
        created = client.post("/v1/admin/connectors", headers=AUTH_HEADERS, json=base)
        assert created.status_code == 201
        assert created.json()["credential_reference"] == "env://HUBSPOT_ACCESS_TOKEN"
        assert "tenant_id" not in created.json()

        write_scope = client.post(
            "/v1/admin/connectors",
            headers=AUTH_HEADERS,
            json={**base, "granted_scopes": ["crm.objects.companies.write"]},
        )
        assert write_scope.status_code == 422

        inline_secret = client.post(
            "/v1/admin/connectors",
            headers=AUTH_HEADERS,
            json={**base, "settings": {"api_key": "must-not-be-here"}},
        )
        assert inline_secret.status_code == 422
    finally:
        main.app.state.store = original_store
        store.close()


def test_action_draft_api_never_executes_external_write(monkeypatch) -> None:
    original_store = main.app.state.store
    store = PersistentStore(":memory:")
    main.app.state.store = store
    client = TestClient(main.app)
    monkeypatch.setenv("DEV_USER_ROLES", "tenant_admin,support_agent")
    identity = main.RequestIdentity(
        tenant_id="tenant_acme_cn",
        user_id="local-admin",
        roles=frozenset({"tenant_admin", "support_agent"}),
    )
    draft = store.create_action_draft(
        identity,
        thread_id=None,
        action_type="create_support_ticket",
        parameters={"summary": "API timeout"},
    )

    try:
        submitted = client.post(
            f"/v1/action-drafts/{draft['id']}/submit", headers=AUTH_HEADERS
        )
        assert submitted.status_code == 200
        assert submitted.json()["status"] == "pending_review"

        approved = client.post(
            f"/v1/action-drafts/{draft['id']}/decision",
            headers=AUTH_HEADERS,
            json={"decision": "approved"},
        )
        assert approved.status_code == 200
        body = approved.json()
        assert body["status"] == "approved_for_manual_execution"
        assert body["result"]["executed"] is False
        assert body["external_record_id"] is None
    finally:
        main.app.state.store = original_store
        store.close()
