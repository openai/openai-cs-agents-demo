from datetime import datetime

import pytest
from chatkit.store import NotFoundError
from chatkit.types import ThreadMetadata, UserMessageItem

from enterprise_support.identity import RequestIdentity
from persistent_store import PersistentStore


def _identity(tenant_id: str, user_id: str = "user-1") -> RequestIdentity:
    return RequestIdentity(
        tenant_id=tenant_id,
        user_id=user_id,
        roles=frozenset({"tenant_admin", "knowledge_editor", "knowledge_reviewer"}),
    )


@pytest.mark.asyncio
async def test_threads_are_persistent_and_tenant_isolated(tmp_path) -> None:
    database_path = str(tmp_path / "agent.db")
    tenant_a = _identity("tenant-a")
    tenant_b = _identity("tenant-b")
    tenant_a_other_user = RequestIdentity(
        tenant_id="tenant-a",
        user_id="user-2",
        roles=frozenset({"end_user"}),
    )
    context_a = {"identity": tenant_a}
    context_b = {"identity": tenant_b}

    store = PersistentStore(database_path)
    thread = ThreadMetadata(id="thr_test", created_at=datetime.now())
    await store.save_thread(thread, context_a)
    store.save_conversation_state(
        thread.id,
        {"current_agent_name": "Triage Agent", "context": {}},
        context_a,
    )
    store.close()

    reopened = PersistentStore(database_path)
    assert (await reopened.load_thread(thread.id, context_a)).id == thread.id
    assert reopened.load_conversation_state(thread.id, context_a) is not None
    with pytest.raises(NotFoundError):
        await reopened.load_thread(thread.id, context_b)
    with pytest.raises(NotFoundError):
        await reopened.load_thread(
            thread.id, {"identity": tenant_a_other_user}
        )
    reopened.close()


def test_knowledge_search_has_no_unrelated_fallback() -> None:
    store = PersistentStore(":memory:")
    identity = _identity("tenant-a")

    assert store.search_knowledge(identity, "DeepSeek 售后服务政策") == []

    document = store.create_document(
        identity,
        title="DeepSeek 企业售后政策",
        content="企业客户可通过专属工单渠道获得技术支持。",
    )
    assert store.search_knowledge(identity, "DeepSeek 售后服务政策") == []

    store.publish_document(identity, document["id"])
    results = store.search_knowledge(identity, "DeepSeek 售后服务政策")

    assert results[0]["document_id"] == document["id"]
    assert results[0]["source_scope"] == "tenant"
    assert results[0]["retrieval"] == "hybrid"
    assert set(results[0]["score_components"]) == {"lexical", "vector", "phrase"}
    store.close()


def test_hybrid_knowledge_search_uses_vector_features_for_near_matches() -> None:
    store = PersistentStore(":memory:")
    identity = _identity("tenant-a")
    document = store.create_document(
        identity,
        title="API retry guide",
        content="Retry timeout handling uses exponential backoff with jitter.",
    )
    store.publish_document(identity, document["id"])

    results = store.search_knowledge(identity, "timeouts retries guidance")

    assert results[0]["document_id"] == document["id"]
    assert results[0]["retrieval"] == "hybrid"
    assert results[0]["score_components"]["lexical"] == 0
    assert results[0]["score_components"]["vector"] > 0
    store.close()


@pytest.mark.asyncio
async def test_action_draft_requires_review_and_manual_external_completion() -> None:
    store = PersistentStore(":memory:")
    identity = _identity("tenant-a")
    context = {"identity": identity}
    thread = ThreadMetadata(id="thr_approval", created_at=datetime.now())

    await store.save_thread(thread, context)
    store.save_conversation_state(
        thread.id,
        {
            "current_agent_name": "Technical Support Agent",
            "context": {"human_approval_required": True},
        },
        context,
    )

    approval = store.create_approval(
        identity,
        thread_id=thread.id,
        action="create_support_ticket",
        parameters={"severity": "SEV-2"},
    )

    assert approval["status"] == "draft"
    assert approval["result"] is None

    submitted = store.submit_action_draft(identity, approval["id"])
    assert submitted["status"] == "pending_review"

    decided = store.decide_approval(identity, approval["id"], "approved")

    assert decided["status"] == "approved_for_manual_execution"
    assert decided["result"]["executed"] is False
    assert decided["result"]["mode"] == "draft_only"
    assert decided["external_record_id"] is None
    persisted = store.load_conversation_state(thread.id, context)
    assert persisted["context"]["human_approval_required"] is True

    completed = store.complete_action_draft(
        identity,
        approval["id"],
        external_record_id="SUP-1042",
    )
    assert completed["status"] == "manually_completed"
    assert completed["external_record_id"] == "SUP-1042"
    persisted = store.load_conversation_state(thread.id, context)
    assert persisted["context"]["human_approval_required"] is False
    assert persisted["context"]["ticket_id"] == "SUP-1042"
    store.close()


def test_action_draft_payload_is_encrypted_and_idempotent() -> None:
    store = PersistentStore(":memory:")
    identity = _identity("tenant-a")
    parameters = {"issue_summary": "customer secret incident", "severity": "SEV-1"}

    first = store.create_action_draft(
        identity,
        thread_id="thread-a",
        action_type="create_support_ticket",
        parameters=parameters,
    )
    second = store.create_action_draft(
        identity,
        thread_id="thread-a",
        action_type="create_support_ticket",
        parameters=parameters,
    )
    raw = store._conn.execute(
        "SELECT payload_encrypted FROM action_drafts WHERE id = ?", (first["id"],)
    ).fetchone()

    assert second["id"] == first["id"]
    assert "customer secret incident" not in raw["payload_encrypted"]
    assert first["parameters"] == parameters
    store.close()


def test_connectors_are_tenant_scoped() -> None:
    store = PersistentStore(":memory:")
    tenant_a = _identity("tenant-a")
    tenant_b = _identity("tenant-b")

    connector = store.configure_connector(
        tenant_a,
        connector_type="crm",
        provider="hubspot",
        environment="sandbox",
        status="enabled",
        credential_reference="env://HUBSPOT_ACCESS_TOKEN",
        granted_scopes=["crm.objects.companies.read"],
        settings={"company_id": "123"},
    )

    assert store.get_enabled_connector(tenant_a, "crm")["id"] == connector["id"]
    assert store.get_enabled_connector(tenant_b, "crm") is None
    with pytest.raises(KeyError):
        store.get_connector(tenant_b, connector["id"])
    store.close()


def test_disabled_oidc_member_is_rejected() -> None:
    store = PersistentStore(":memory:")
    administrator = _identity("tenant-a", "admin")
    member = RequestIdentity(
        tenant_id="tenant-a",
        user_id="member-a",
        roles=frozenset({"end_user"}),
    )
    store.authorize_identity(administrator)
    store.authorize_identity(member)

    updated = store.update_member(
        administrator,
        member.user_id,
        status="disabled",
        roles=["end_user"],
    )

    assert updated["status"] == "disabled"
    with pytest.raises(PermissionError):
        store.authorize_identity(member)
    store.close()


def test_external_document_sync_preserves_versions_and_requires_review() -> None:
    store = PersistentStore(":memory:")
    identity = _identity("tenant-a")

    first = store.sync_external_document(
        identity,
        title="Confluence 产品政策",
        content="第一版已审核内容",
        source="confluence:100",
    )
    assert first["status"] == "review_pending"
    store.publish_document(identity, first["id"])

    unchanged = store.sync_external_document(
        identity,
        title="Confluence 产品政策",
        content="第一版已审核内容",
        source="confluence:100",
    )
    assert unchanged["sync_status"] == "unchanged"

    second = store.sync_external_document(
        identity,
        title="Confluence 产品政策",
        content="第二版尚待审核内容",
        source="confluence:100",
    )
    old_version = store.get_document_version(identity, first["id"], 1)

    assert second["version"] == 2
    assert second["status"] == "review_pending"
    assert old_version["content"] == "第一版已审核内容"
    assert old_version["status"] == "published"
    assert store.search_knowledge(identity, "第二版尚待审核内容") == []
    store.close()


@pytest.mark.asyncio
async def test_portal_thread_summaries_are_owner_scoped() -> None:
    store = PersistentStore(":memory:")
    owner = RequestIdentity(
        tenant_id="tenant-a",
        user_id="owner-a",
        roles=frozenset({"tenant_admin", "end_user"}),
    )
    other_user = RequestIdentity(
        tenant_id="tenant-a",
        user_id="owner-b",
        roles=frozenset({"end_user"}),
    )

    for identity, thread_id, question in (
        (owner, "thr_owner", "我们的 API 持续出现 429，请帮助排查。"),
        (other_user, "thr_other", "另一位用户的私有问题"),
    ):
        context = {"identity": identity}
        thread = ThreadMetadata(id=thread_id, created_at=datetime.now())
        await store.save_thread(thread, context)
        message = UserMessageItem.model_validate(
            {
                "id": f"msg_{thread_id}",
                "thread_id": thread_id,
                "created_at": datetime.now(),
                "content": [{"type": "input_text", "text": question}],
                "inference_options": {},
            }
        )
        await store.save_item(thread_id, message, context)

    await store.save_thread(
        ThreadMetadata(id="thr_empty", created_at=datetime.now()),
        {"identity": owner},
    )

    result = store.list_portal_thread_summaries(owner)

    assert [item["id"] for item in result["data"]] == ["thr_owner"]
    assert result["data"][0]["title"] == "我们的 API 持续出现 429，请帮助排查。"
    assert result["data"][0]["preview"] == "我们的 API 持续出现 429，请帮助排查。"
    assert "tenant_id" not in result["data"][0]
    store.close()
