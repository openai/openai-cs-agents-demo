import os
from datetime import datetime
from uuid import uuid4

import pytest
from chatkit.types import ThreadMetadata

from enterprise_support.identity import RequestIdentity
from persistent_store import PersistentStore


POSTGRES_URL = os.getenv("TEST_POSTGRES_URL")


@pytest.mark.skipif(not POSTGRES_URL, reason="TEST_POSTGRES_URL is not configured")
@pytest.mark.asyncio
async def test_postgres_store_supports_production_foundation() -> None:
    suffix = uuid4().hex[:8]
    identity = RequestIdentity(
        tenant_id=f"tenant-pg-{suffix}",
        user_id="pg-admin",
        roles=frozenset({"tenant_admin", "knowledge_editor", "knowledge_reviewer", "support_agent"}),
    )
    store = PersistentStore(POSTGRES_URL)
    thread = ThreadMetadata(id=f"thr_pg_{suffix}", created_at=datetime.now())
    await store.save_thread(thread, {"identity": identity})
    document = store.create_document(
        identity,
        title="PostgreSQL integration document",
        content="Persistent production test content.",
    )
    connector = store.configure_connector(
        identity,
        connector_type="crm",
        provider="hubspot",
        environment="sandbox",
        status="enabled",
        credential_reference="env://HUBSPOT_ACCESS_TOKEN",
        granted_scopes=["crm.objects.companies.read"],
        settings={"company_id": "123"},
    )
    draft = store.create_action_draft(
        identity,
        thread_id=thread.id,
        action_type="create_support_ticket",
        parameters={"summary": "PostgreSQL integration"},
    )
    trace = store.record_trace(
        identity,
        request_id=f"req_pg_{suffix}",
        thread_id=thread.id,
        model="glm-test",
        agent_name="Technical Support Agent",
        status="success",
        duration_ms=100,
        event_summary={"tool_names": ["create_support_ticket"]},
    )
    store.close()

    reopened = PersistentStore(POSTGRES_URL)
    assert (await reopened.load_thread(thread.id, {"identity": identity})).id == thread.id
    assert reopened.get_document(identity, document["id"])["title"] == document["title"]
    assert reopened.get_connector(identity, connector["id"])["provider"] == "hubspot"
    assert reopened.list_action_drafts(identity)[0]["id"] == draft["id"]
    assert reopened.list_traces(identity)[0]["id"] == trace["id"]
    reopened.close()
