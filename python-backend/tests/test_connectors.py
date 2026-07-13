import pytest

from enterprise_support.connectors import (
    ConnectorError,
    ConnectorGateway,
    ReadOnlyHttpClient,
    validate_read_only_scopes,
)
from enterprise_support.identity import RequestIdentity
from persistent_store import PersistentStore


def test_scope_validation_allows_known_reads_and_rejects_writes() -> None:
    validate_read_only_scopes("hubspot", ["crm.objects.companies.read"])

    with pytest.raises(ValueError, match="Write-capable"):
        validate_read_only_scopes("hubspot", ["crm.objects.companies.write"])


def test_production_usage_host_requires_allowlist(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("CONNECTOR_ALLOWED_HOSTS", raising=False)

    with pytest.raises(ConnectorError, match="not in CONNECTOR_ALLOWED_HOSTS"):
        ReadOnlyHttpClient(
            base_url="https://usage.example.com",
            provider="usage_api",
            headers={},
        )


def test_connector_transport_exposes_get_only() -> None:
    assert hasattr(ReadOnlyHttpClient, "get_json")
    assert not hasattr(ReadOnlyHttpClient, "post")
    assert not hasattr(ReadOnlyHttpClient, "put")
    assert not hasattr(ReadOnlyHttpClient, "delete")


def test_gray_release_user_filter_is_enforced() -> None:
    store = PersistentStore(":memory:")
    admin = RequestIdentity(
        tenant_id="tenant-a",
        user_id="admin",
        roles=frozenset({"tenant_admin"}),
    )
    denied_user = RequestIdentity(
        tenant_id="tenant-a",
        user_id="not-in-pilot",
        roles=frozenset({"end_user"}),
    )
    store.configure_connector(
        admin,
        connector_type="crm",
        provider="hubspot",
        environment="sandbox",
        status="enabled",
        credential_reference="env://HUBSPOT_ACCESS_TOKEN",
        granted_scopes=["crm.objects.companies.read"],
        settings={"company_id": "123", "allowed_user_ids": "pilot-user"},
    )

    with pytest.raises(ConnectorError, match="gray-release user"):
        ConnectorGateway(store)._connector(denied_user, "crm")
    store.close()


@pytest.mark.asyncio
async def test_confluence_sync_creates_review_pending_documents(monkeypatch) -> None:
    store = PersistentStore(":memory:")
    identity = RequestIdentity(
        tenant_id="tenant-a",
        user_id="admin",
        roles=frozenset({"tenant_admin", "knowledge_editor", "knowledge_reviewer"}),
    )
    gateway = ConnectorGateway(store)

    async def read_documents(_identity):
        return {
            "status": "ok",
            "results": [
                {
                    "id": "100",
                    "title": "产品指南",
                    "body_html": "<h1>产品指南</h1><p>仅供审核的同步内容。</p>",
                }
            ],
        }

    monkeypatch.setattr(gateway, "read_documents", read_documents)

    result = await gateway.sync_documents(identity)

    assert result["status"] == "completed"
    assert result["synced"][0]["status"] == "review_pending"
    assert store.list_documents(identity)[0]["source"] == "confluence:100"
    store.close()
