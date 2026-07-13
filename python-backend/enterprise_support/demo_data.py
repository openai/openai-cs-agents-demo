from __future__ import annotations

from copy import deepcopy
from typing import Any

from .context import EnterpriseAgentContext


DEMO_ACCOUNTS: dict[str, dict[str, Any]] = {
    "acme": {
        "customer_name": "Lin Chen",
        "company_name": "Acme Intelligence",
        "account_id": "ACC-10086",
        "tenant_id": "tenant_acme_cn",
        "plan": "Enterprise",
        "deployment_environment": "Private VPC",
        "product_area": "Agent Platform",
        "billing": {
            "currency": "CNY",
            "current_month_usage": 186420,
            "included_usage": 250000,
            "invoice_status": "Paid",
            "renewal_date": "2026-12-01",
        },
    },
    "startup": {
        "customer_name": "Alex Wang",
        "company_name": "Nova Labs",
        "account_id": "ACC-2048",
        "tenant_id": "tenant_nova",
        "plan": "Growth",
        "deployment_environment": "Cloud",
        "product_area": "Model API",
        "billing": {
            "currency": "CNY",
            "current_month_usage": 32750,
            "included_usage": 50000,
            "invoice_status": "Open",
            "renewal_date": "2026-09-15",
        },
    },
}


KNOWLEDGE_BASE: list[dict[str, str]] = [
    {
        "id": "KB-PLATFORM-001",
        "title": "Agent Platform overview",
        "keywords": "agent workflow handoff tool orchestration tracing",
        "content": "The Agent Platform supports specialist handoffs, tool execution, streaming, and trace-based debugging.",
    },
    {
        "id": "KB-API-003",
        "title": "Model API reliability guide",
        "keywords": "api timeout latency rate limit retry 429 5xx",
        "content": "Use exponential backoff with jitter for transient 429 and 5xx responses. Persist request IDs for support diagnostics.",
    },
    {
        "id": "KB-RAG-007",
        "title": "Enterprise knowledge retrieval",
        "keywords": "rag knowledge base retrieval citation document permission",
        "content": "Retrieval must preserve document-level permissions and return source identifiers with every grounded answer.",
    },
    {
        "id": "KB-SEC-010",
        "title": "Security and data controls",
        "keywords": "security privacy encryption retention sso rbacs audit private vpc",
        "content": "Enterprise deployments support SSO, role-based access, audit logs, configurable retention, and private network patterns.",
    },
    {
        "id": "KB-BILLING-004",
        "title": "Usage and billing",
        "keywords": "billing usage invoice quota plan token cost",
        "content": "Usage is aggregated by tenant and project. Billing disputes require a billing case with the affected period and project ID.",
    },
]


COMPLIANCE_LIBRARY: dict[str, dict[str, str]] = {
    "soc2": {
        "id": "SEC-SOC2-001",
        "summary": "A current SOC 2 report can be shared through the controlled trust-center workflow under NDA.",
    },
    "iso27001": {
        "id": "SEC-ISO-001",
        "summary": "The information security management scope and certificate are available through the trust center.",
    },
    "data retention": {
        "id": "SEC-RET-002",
        "summary": "Retention is configurable by product and contract. Confirm the tenant policy before stating a duration.",
    },
    "private deployment": {
        "id": "SEC-DEPLOY-004",
        "summary": "Private VPC and controlled egress patterns are available for qualified enterprise deployments.",
    },
}


def resolve_demo_account(query: str | None) -> tuple[str, dict[str, Any]]:
    normalized = (query or "").lower()
    if any(token in normalized for token in ("nova", "2048", "startup")):
        return "startup", deepcopy(DEMO_ACCOUNTS["startup"])
    return "acme", deepcopy(DEMO_ACCOUNTS["acme"])


def resolve_demo_account_for_tenant(tenant_id: str) -> tuple[str, dict[str, Any]]:
    for key, account in DEMO_ACCOUNTS.items():
        if account["tenant_id"] == tenant_id:
            return key, deepcopy(account)
    raise KeyError(f"No demo account is configured for tenant {tenant_id}")


def hydrate_account(
    ctx: EnterpriseAgentContext,
    query: str | None = None,
    *,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    key, account = (
        resolve_demo_account_for_tenant(tenant_id)
        if tenant_id
        else resolve_demo_account(query)
    )
    for field in (
        "customer_name",
        "company_name",
        "account_id",
        "tenant_id",
        "plan",
        "deployment_environment",
        "product_area",
    ):
        if getattr(ctx, field) is None:
            setattr(ctx, field, account[field])
    ctx.verified_identity = True
    return {"key": key, **account}


def search_knowledge(query: str, limit: int = 3) -> list[dict[str, str]]:
    terms = {term for term in query.lower().replace("/", " ").split() if len(term) > 2}
    scored: list[tuple[int, dict[str, str]]] = []
    for item in KNOWLEDGE_BASE:
        haystack = " ".join(item.values()).lower()
        score = sum(term in haystack for term in terms)
        scored.append((score, item))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    matches = [deepcopy(item) for score, item in scored if score > 0][:limit]
    return matches
