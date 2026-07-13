from __future__ import annotations

import base64
import os
import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urljoin, urlparse

import httpx

from .identity import RequestIdentity
from .observability import METRICS
from .security import redact_data


READ_ONLY_SCOPES = {
    "hubspot": frozenset({"crm.objects.companies.read", "crm.objects.contacts.read"}),
    "jira": frozenset({"read:jira-work", "read:issue:jira", "read:project:jira"}),
    "usage_api": frozenset({"usage:read", "billing:read"}),
    "confluence": frozenset({"read:page:confluence", "read:space:confluence", "read:content:confluence"}),
}
_WRITE_SCOPE_MARKERS = ("write", "create", "edit", "delete", "manage", "admin")
_SECRET_REFERENCE = re.compile(r"^env://([A-Z][A-Z0-9_]*)$")


class ConnectorError(RuntimeError):
    def __init__(self, status: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.status = status
        self.retryable = retryable

    def as_dict(self) -> dict[str, Any]:
        return {"status": self.status, "message": str(self), "retryable": self.retryable}


def validate_read_only_scopes(provider: str, scopes: list[str]) -> None:
    normalized = {scope.strip() for scope in scopes if scope.strip()}
    if any(marker in scope.lower() for scope in normalized for marker in _WRITE_SCOPE_MARKERS):
        raise ValueError("Write-capable connector scopes are forbidden")
    allowed = READ_ONLY_SCOPES.get(provider)
    if allowed is None:
        raise ValueError(f"Unsupported connector provider: {provider}")
    unexpected = normalized.difference(allowed)
    if unexpected:
        raise ValueError(f"Unsupported scopes for {provider}: {', '.join(sorted(unexpected))}")


def resolve_secret(reference: str) -> str:
    match = _SECRET_REFERENCE.fullmatch(reference)
    if not match:
        raise ConnectorError("configuration_error", "Credential reference must use env://NAME")
    value = os.getenv(match.group(1))
    if not value:
        raise ConnectorError("configuration_error", "Configured credential is unavailable")
    return value


def _validated_base_url(value: str, provider: str) -> str:
    parsed = urlparse(value)
    is_production = os.getenv("APP_ENV", "development") == "production"
    if parsed.scheme not in ({"https"} if is_production else {"http", "https"}) or not parsed.hostname:
        raise ConnectorError("configuration_error", "Connector base URL is invalid")
    host = parsed.hostname.lower()
    if provider in {"jira", "confluence"} and not (
        host.endswith(".atlassian.net") or (not is_production and host in {"localhost", "127.0.0.1"})
    ):
        raise ConnectorError("configuration_error", "Atlassian connector host is not allowed")
    if provider == "hubspot" and host != "api.hubapi.com" and is_production:
        raise ConnectorError("configuration_error", "HubSpot connector host is not allowed")
    allowed_hosts = {item.strip().lower() for item in os.getenv("CONNECTOR_ALLOWED_HOSTS", "").split(",") if item.strip()}
    if provider == "usage_api" and is_production and host not in allowed_hosts:
        raise ConnectorError("configuration_error", "Usage API host is not in CONNECTOR_ALLOWED_HOSTS")
    return value.rstrip("/") + "/"


class ReadOnlyHttpClient:
    """Connector transport intentionally exposes GET only."""

    def __init__(self, *, base_url: str, provider: str, headers: dict[str, str], timeout: float = 3.0) -> None:
        self.base_url = _validated_base_url(base_url, provider)
        self.provider = provider
        self.headers = headers
        self.timeout = min(max(timeout, 0.5), 10.0)

    async def get_json(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = urljoin(self.base_url, path.lstrip("/"))
        if urlparse(url).netloc != urlparse(self.base_url).netloc:
            raise ConnectorError("configuration_error", "Connector request cannot leave the configured host")
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(follow_redirects=False, timeout=self.timeout) as client:
                response = await client.get(url, params=params, headers=self.headers)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            METRICS.increment("enterprise_agent_connector_requests_total", provider=self.provider, status="unavailable")
            raise ConnectorError("connector_unavailable", "Connector request failed", retryable=True) from exc
        elapsed = time.perf_counter() - started
        METRICS.observe("enterprise_agent_connector_request_duration_seconds", elapsed, provider=self.provider)
        if response.status_code == 429:
            METRICS.increment("enterprise_agent_connector_requests_total", provider=self.provider, status="rate_limited")
            raise ConnectorError("rate_limited", "Connector rate limit reached", retryable=True)
        if response.status_code in {401, 403}:
            METRICS.increment("enterprise_agent_connector_requests_total", provider=self.provider, status="forbidden")
            raise ConnectorError("forbidden", "Connector credentials or permissions were rejected")
        if response.status_code == 404:
            METRICS.increment("enterprise_agent_connector_requests_total", provider=self.provider, status="not_found")
            return {"status": "not_found"}
        if response.status_code >= 500:
            METRICS.increment("enterprise_agent_connector_requests_total", provider=self.provider, status="unavailable")
            raise ConnectorError("connector_unavailable", "Connector service is unavailable", retryable=True)
        if response.status_code >= 400:
            METRICS.increment("enterprise_agent_connector_requests_total", provider=self.provider, status="error")
            raise ConnectorError("connector_error", f"Connector returned HTTP {response.status_code}")
        try:
            body = response.json()
        except ValueError as exc:
            raise ConnectorError("connector_error", "Connector returned invalid JSON") from exc
        if not isinstance(body, dict):
            raise ConnectorError("connector_error", "Connector response must be a JSON object")
        METRICS.increment("enterprise_agent_connector_requests_total", provider=self.provider, status="success")
        return body


@dataclass(frozen=True)
class ConnectorConfig:
    id: str
    tenant_id: str
    connector_type: str
    provider: str
    environment: str
    status: str
    credential_reference: str
    granted_scopes: list[str]
    settings: dict[str, Any]

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> "ConnectorConfig":
        return cls(
            id=record["id"],
            tenant_id=record["tenant_id"],
            connector_type=record["connector_type"],
            provider=record["provider"],
            environment=record["environment"],
            status=record["status"],
            credential_reference=record["credential_reference"],
            granted_scopes=list(record.get("granted_scopes", [])),
            settings=dict(record.get("settings", {})),
        )


class BaseConnector:
    def __init__(self, config: ConnectorConfig) -> None:
        self.config = config
        validate_read_only_scopes(config.provider, config.granted_scopes)

    def _bearer_client(self, default_base_url: str) -> ReadOnlyHttpClient:
        token = resolve_secret(self.config.credential_reference)
        return ReadOnlyHttpClient(
            base_url=str(self.config.settings.get("base_url") or default_base_url),
            provider=self.config.provider,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        )

    def _atlassian_client(self) -> ReadOnlyHttpClient:
        token = resolve_secret(self.config.credential_reference)
        email = str(self.config.settings.get("account_email") or "")
        if not email:
            raise ConnectorError("configuration_error", "Atlassian account_email is required")
        encoded = base64.b64encode(f"{email}:{token}".encode()).decode()
        return ReadOnlyHttpClient(
            base_url=str(self.config.settings.get("base_url") or ""),
            provider=self.config.provider,
            headers={"Authorization": f"Basic {encoded}", "Accept": "application/json"},
        )


class HubSpotCRMConnector(BaseConnector):
    async def read_account(self, identity: RequestIdentity) -> dict[str, Any]:
        company_id = str(self.config.settings.get("company_id") or "")
        if not company_id:
            raise ConnectorError("configuration_error", "A trusted HubSpot company_id mapping is required")
        body = await self._bearer_client("https://api.hubapi.com/").get_json(
            f"crm/v3/objects/companies/{quote(company_id, safe='')}",
            params={"properties": "name,domain,customer_tier,contract_status,hs_lastmodifieddate"},
        )
        if body.get("status") == "not_found":
            return body
        props = body.get("properties") if isinstance(body.get("properties"), dict) else {}
        return {
            "status": "ok",
            "account_id": body.get("id"),
            "company_name": props.get("name"),
            "domain": props.get("domain"),
            "customer_tier": props.get("customer_tier"),
            "contract_status": props.get("contract_status"),
            "source_updated_at": props.get("hs_lastmodifieddate") or body.get("updatedAt"),
        }


class JiraTicketConnector(BaseConnector):
    async def read_ticket(self, ticket_key: str) -> dict[str, Any]:
        if not re.fullmatch(r"[A-Z][A-Z0-9]+-\d+", ticket_key.upper()):
            raise ConnectorError("invalid_request", "Ticket key is invalid")
        body = await self._atlassian_client().get_json(
            f"rest/api/3/issue/{quote(ticket_key.upper(), safe='-')}",
            params={"fields": "summary,status,priority,updated,comment"},
        )
        if body.get("status") == "not_found":
            return body
        fields = body.get("fields") if isinstance(body.get("fields"), dict) else {}
        status = fields.get("status") if isinstance(fields.get("status"), dict) else {}
        priority = fields.get("priority") if isinstance(fields.get("priority"), dict) else {}
        return {
            "status": "ok",
            "ticket_key": body.get("key"),
            "summary": fields.get("summary"),
            "ticket_status": status.get("name"),
            "priority": priority.get("name"),
            "source_updated_at": fields.get("updated"),
        }


class UsageAPIConnector(BaseConnector):
    async def read_usage(self, identity: RequestIdentity) -> dict[str, Any]:
        account_id = str(self.config.settings.get("account_id") or "")
        if not account_id:
            raise ConnectorError("configuration_error", "A trusted usage account_id mapping is required")
        path = str(self.config.settings.get("usage_path") or "/v1/usage")
        body = await self._bearer_client(str(self.config.settings.get("base_url") or "")).get_json(
            path,
            params={"account_id": account_id},
        )
        allowed = {
            "account_id",
            "plan",
            "period_start",
            "period_end",
            "usage",
            "quota",
            "remaining",
            "currency",
            "amount_due",
            "renewal_date",
            "source_updated_at",
        }
        return {"status": "ok", **{key: value for key, value in body.items() if key in allowed}}


class ConfluenceDocumentConnector(BaseConnector):
    async def read_pages(self) -> dict[str, Any]:
        space_id = str(self.config.settings.get("space_id") or "")
        if not space_id:
            raise ConnectorError("configuration_error", "Confluence space_id is required")
        body = await self._atlassian_client().get_json(
            "wiki/api/v2/pages",
            params={"space-id": space_id, "limit": min(int(self.config.settings.get("limit", 25)), 100), "body-format": "storage"},
        )
        pages = body.get("results") if isinstance(body.get("results"), list) else []
        return {
            "status": "ok",
            "results": [
                redact_data(
                    {
                        "id": page.get("id"),
                        "title": page.get("title"),
                        "status": page.get("status"),
                        "version": page.get("version"),
                        "body_html": (
                            page.get("body", {}).get("storage", {}).get("value", "")
                            if isinstance(page.get("body"), dict)
                            else ""
                        ),
                    }
                )
                for page in pages
                if isinstance(page, dict)
            ],
        }


CONNECTOR_CLASSES = {
    "hubspot": HubSpotCRMConnector,
    "jira": JiraTicketConnector,
    "usage_api": UsageAPIConnector,
    "confluence": ConfluenceDocumentConnector,
}


class ConnectorGateway:
    def __init__(self, store: Any) -> None:
        self.store = store

    def _connector(self, identity: RequestIdentity, connector_type: str) -> BaseConnector:
        record = self.store.get_enabled_connector(identity, connector_type)
        if record is None:
            raise ConnectorError("integration_unavailable", f"No enabled {connector_type} connector is configured")
        raw_allowed_users = record.get("settings", {}).get("allowed_user_ids", "")
        if isinstance(raw_allowed_users, str):
            allowed_users = {item.strip() for item in raw_allowed_users.split(",") if item.strip()}
        elif isinstance(raw_allowed_users, list):
            allowed_users = {str(item) for item in raw_allowed_users}
        else:
            allowed_users = set()
        if allowed_users and identity.user_id not in allowed_users:
            raise ConnectorError("forbidden", "Connector is not enabled for this gray-release user")
        config = ConnectorConfig.from_record(record)
        connector_class = CONNECTOR_CLASSES.get(config.provider)
        if connector_class is None:
            raise ConnectorError("configuration_error", "Connector provider is unsupported")
        return connector_class(config)

    async def read_account(self, identity: RequestIdentity) -> dict[str, Any]:
        connector = self._connector(identity, "crm")
        if not isinstance(connector, HubSpotCRMConnector):
            raise ConnectorError("configuration_error", "CRM provider does not support account reads")
        return await connector.read_account(identity)

    async def read_ticket(self, identity: RequestIdentity, ticket_key: str) -> dict[str, Any]:
        connector = self._connector(identity, "ticketing")
        if not isinstance(connector, JiraTicketConnector):
            raise ConnectorError("configuration_error", "Ticket provider does not support ticket reads")
        return await connector.read_ticket(ticket_key)

    async def read_usage(self, identity: RequestIdentity) -> dict[str, Any]:
        connector = self._connector(identity, "usage")
        if not isinstance(connector, UsageAPIConnector):
            raise ConnectorError("configuration_error", "Usage provider does not support usage reads")
        return await connector.read_usage(identity)

    async def read_documents(self, identity: RequestIdentity) -> dict[str, Any]:
        connector = self._connector(identity, "documents")
        if not isinstance(connector, ConfluenceDocumentConnector):
            raise ConnectorError("configuration_error", "Document provider does not support page reads")
        return await connector.read_pages()

    async def sync_documents(self, identity: RequestIdentity) -> dict[str, Any]:
        from .documents import extract_document_text

        response = await self.read_documents(identity)
        synced: list[dict[str, Any]] = []
        skipped = 0
        for page in response.get("results", []):
            page_id = str(page.get("id") or "")
            body_html = str(page.get("body_html") or "")
            if not page_id or not body_html:
                skipped += 1
                continue
            content = extract_document_text(f"{page_id}.html", body_html.encode("utf-8"))
            if not content:
                skipped += 1
                continue
            document = self.store.sync_external_document(
                identity,
                title=str(page.get("title") or f"Confluence {page_id}"),
                content=content,
                source=f"confluence:{page_id}",
            )
            synced.append(
                {
                    "document_id": document["id"],
                    "version": document["version"],
                    "status": document["status"],
                    "sync_status": document["sync_status"],
                }
            )
        return {"status": "completed", "synced": synced, "skipped": skipped}

    async def test_connector(self, identity: RequestIdentity, connector_id: str) -> dict[str, Any]:
        record = self.store.get_connector(identity, connector_id)
        config = ConnectorConfig.from_record(record)
        connector_class = CONNECTOR_CLASSES.get(config.provider)
        if connector_class is None:
            raise ConnectorError("configuration_error", "Connector provider is unsupported")
        connector = connector_class(config)
        connector_type = record["connector_type"]
        try:
            if connector_type == "crm":
                if not isinstance(connector, HubSpotCRMConnector):
                    raise ConnectorError("configuration_error", "CRM provider is invalid")
                result = await connector.read_account(identity)
            elif connector_type == "usage":
                if not isinstance(connector, UsageAPIConnector):
                    raise ConnectorError("configuration_error", "Usage provider is invalid")
                result = await connector.read_usage(identity)
            elif connector_type == "documents":
                if not isinstance(connector, ConfluenceDocumentConnector):
                    raise ConnectorError("configuration_error", "Document provider is invalid")
                result = await connector.read_pages()
            elif connector_type == "ticketing":
                sample_key = str(record.get("settings", {}).get("sample_ticket_key") or "")
                if not sample_key:
                    raise ConnectorError("configuration_error", "sample_ticket_key is required for a Jira test")
                if not isinstance(connector, JiraTicketConnector):
                    raise ConnectorError("configuration_error", "Ticket provider is invalid")
                result = await connector.read_ticket(sample_key)
            else:
                raise ConnectorError("configuration_error", "Connector type is unsupported")
        except ConnectorError as exc:
            self.store.record_connector_health(identity, connector_id, status="error", error_status=exc.status)
            raise
        self.store.record_connector_health(identity, connector_id, status="healthy", error_status=None)
        return {"status": "healthy", "connector_id": connector_id, "sample": redact_data(result, mask_personal_data=True)}
