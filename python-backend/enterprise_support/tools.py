from __future__ import annotations

import json
import os

from agents import RunContextWrapper, function_tool
from chatkit.types import ProgressUpdateEvent

from .context import EnterpriseAgentChatContext
from .connectors import ConnectorError, ConnectorGateway
from .demo_data import COMPLIANCE_LIBRARY, hydrate_account, search_knowledge
from .identity import identity_from_context
from .observability import METRICS


def _json(data: dict | list) -> str:
    return json.dumps(data, ensure_ascii=False)


def _runtime(context: RunContextWrapper[EnterpriseAgentChatContext]):
    chat_context = context.context
    identity = identity_from_context(chat_context.request_context)
    return chat_context, identity, chat_context.store


def _gateway(store) -> ConnectorGateway:
    gateway = getattr(store, "connector_gateway", None)
    return gateway if isinstance(gateway, ConnectorGateway) else ConnectorGateway(store)


def _demo_mode() -> bool:
    return (
        os.getenv("APP_ENV", "development") != "production"
        and os.getenv("CONNECTOR_MODE", "demo") == "demo"
    )


@function_tool(
    name_override="identify_customer_account",
    description_override="Read the authenticated customer's account from the configured read-only CRM connector.",
)
async def identify_customer_account(
    context: RunContextWrapper[EnterpriseAgentChatContext], query: str = "Acme"
) -> str:
    _, identity, store = _runtime(context)
    try:
        account = await _gateway(store).read_account(identity)
        if account.get("status") == "not_found":
            return _json(account)
        state = context.context.state
        state.account_id = str(account.get("account_id") or "") or None
        state.company_name = account.get("company_name")
        state.plan = account.get("customer_tier")
        state.verified_identity = True
        return _json({**account, "identity_verified": True, "source": "crm"})
    except ConnectorError as exc:
        if not _demo_mode() or exc.status != "integration_unavailable":
            return _json(exc.as_dict())
    try:
        account = hydrate_account(
            context.context.state, query, tenant_id=identity.tenant_id
        )
    except KeyError:
        return _json(
            {
                "status": "integration_unavailable",
                "message": "No account system is configured for this tenant.",
            }
        )
    return _json(
        {
            "status": "ok",
            "account_id": account["account_id"],
            "company_name": account["company_name"],
            "plan": account["plan"],
            "deployment_environment": account["deployment_environment"],
            "identity_verified": True,
            "source": "development_demo",
        }
    )


@function_tool(
    name_override="search_product_knowledge",
    description_override="Search approved product documentation and return grounded passages with source IDs.",
)
async def search_product_knowledge(
    context: RunContextWrapper[EnterpriseAgentChatContext], query: str
) -> str:
    await context.context.stream(ProgressUpdateEvent(text="Searching approved knowledge sources..."))
    chat_context, identity, store = _runtime(context)
    if hasattr(store, "search_knowledge"):
        matches = store.search_knowledge(identity, query)
    else:
        matches = search_knowledge(query)
    refs = [item.get("document_id", item.get("id", "")) for item in matches]
    context.context.state.source_refs = list(dict.fromkeys(context.context.state.source_refs + refs))
    if not matches:
        METRICS.increment(
            "enterprise_agent_knowledge_searches_total", status="insufficient_evidence"
        )
        gap = None
        if hasattr(store, "create_knowledge_gap"):
            gap = store.create_knowledge_gap(
                identity,
                query,
                source="agent",
                thread_id=chat_context.thread.id,
            )
        return _json(
            {
                "status": "insufficient_evidence",
                "results": [],
                "knowledge_gap": True,
                "knowledge_gap_id": gap["id"] if gap else None,
                "recommended_action": "offer_human_escalation",
            }
        )
    METRICS.increment("enterprise_agent_knowledge_searches_total", status="grounded")
    return _json(
        {
            "status": "grounded",
            "results": matches,
            "citation_required": True,
            "knowledge_gap": False,
        }
    )


@function_tool(
    name_override="diagnose_technical_issue",
    description_override="Create a structured diagnosis from symptoms without changing customer systems.",
)
async def diagnose_technical_issue(
    context: RunContextWrapper[EnterpriseAgentChatContext],
    symptoms: str,
    environment: str | None = None,
) -> str:
    ctx = context.context.state
    ctx.issue_summary = symptoms
    ctx.deployment_environment = environment or ctx.deployment_environment
    lower = symptoms.lower()
    if any(token in lower for token in ("outage", "down", "all requests", "data loss")):
        ctx.severity = "SEV-1"
        ctx.escalation_required = True
    elif any(token in lower for token in ("429", "timeout", "latency", "5xx")):
        ctx.severity = "SEV-2"
    else:
        ctx.severity = ctx.severity or "SEV-3"
    return _json(
        {
            "severity": ctx.severity,
            "likely_causes": ["rate limiting or transient upstream errors", "client retry configuration"],
            "next_checks": ["capture request IDs", "check error distribution", "verify retry and timeout settings"],
            "system_changed": False,
        }
    )


@function_tool(
    name_override="create_support_ticket",
    description_override="Generate a draft support ticket for human review; never writes to the external ticket system.",
)
async def create_support_ticket(
    context: RunContextWrapper[EnterpriseAgentChatContext],
    issue_summary: str,
    severity: str,
) -> str:
    ctx = context.context.state
    chat_context, identity, store = _runtime(context)
    ctx.human_approval_required = True
    ctx.issue_summary = issue_summary
    ctx.severity = severity
    draft = store.create_action_draft(
        identity,
        thread_id=chat_context.thread.id,
        action_type="create_support_ticket",
        parameters={"issue_summary": issue_summary, "severity": severity},
    )
    METRICS.increment(
        "enterprise_agent_action_drafts_total",
        action="create_support_ticket",
        status="draft",
    )
    return _json(
        {
            "created": False,
            "draft_created": True,
            "draft_id": draft["id"],
            "approval_id": draft["id"],
            "status": "draft",
            "execution_mode": "draft_only",
            "message": "A draft was generated. Approval only sends it to a human execution queue.",
        }
    )


@function_tool(
    name_override="design_solution_architecture",
    description_override="Produce a preliminary AI solution architecture from business and technical requirements.",
)
async def design_solution_architecture(
    context: RunContextWrapper[EnterpriseAgentChatContext],
    requirements: str,
    monthly_users: int = 1000,
    sensitive_data: bool = False,
) -> str:
    ctx = context.context.state
    deployment = "Private VPC with controlled egress" if sensitive_data else "Managed cloud"
    scale = "async queue and horizontal workers" if monthly_users >= 10000 else "stateless API service"
    architecture = f"{deployment}; {scale}; permission-aware retrieval; evaluation and trace pipeline"
    ctx.recommended_architecture = architecture
    ctx.deployment_environment = deployment
    ctx.internal_notes.append(requirements)
    return _json(
        {
            "architecture": architecture,
            "assumptions": {"monthly_users": monthly_users, "sensitive_data": sensitive_data},
            "open_questions": ["target SLA", "data residency", "required integrations"],
            "status": "preliminary",
        }
    )


@function_tool(
    name_override="create_sales_opportunity",
    description_override="Generate a draft CRM opportunity for human review; never writes to CRM.",
)
async def create_sales_opportunity(
    context: RunContextWrapper[EnterpriseAgentChatContext],
    requirements: str,
) -> str:
    ctx = context.context.state
    chat_context, identity, store = _runtime(context)
    ctx.human_approval_required = True
    draft = store.create_action_draft(
        identity,
        thread_id=chat_context.thread.id,
        action_type="create_sales_opportunity",
        parameters={"requirements": requirements},
    )
    METRICS.increment(
        "enterprise_agent_action_drafts_total",
        action="create_sales_opportunity",
        status="draft",
    )
    return _json(
        {
            "created": False,
            "draft_created": True,
            "draft_id": draft["id"],
            "approval_id": draft["id"],
            "status": "draft",
            "execution_mode": "draft_only",
        }
    )


@function_tool(
    name_override="get_billing_summary",
    description_override="Read usage, plan, invoice, and renewal data from the configured read-only usage API.",
)
async def get_billing_summary(
    context: RunContextWrapper[EnterpriseAgentChatContext], account_query: str = "Acme"
) -> str:
    _, identity, store = _runtime(context)
    try:
        usage = await _gateway(store).read_usage(identity)
        if usage.get("account_id"):
            context.context.state.account_id = str(usage["account_id"])
        if usage.get("plan"):
            context.context.state.plan = str(usage["plan"])
        return _json({**usage, "source": "usage_api"})
    except ConnectorError as exc:
        if not _demo_mode() or exc.status != "integration_unavailable":
            return _json(exc.as_dict())
    try:
        account = hydrate_account(
            context.context.state,
            account_query,
            tenant_id=identity.tenant_id,
        )
    except KeyError:
        return _json(
            {
                "status": "integration_unavailable",
                "message": "No billing integration is configured for this tenant.",
            }
        )
    return _json(
        {
            "status": "ok",
            "account_id": account["account_id"],
            "plan": account["plan"],
            **account["billing"],
            "source": "development_demo",
        }
    )


@function_tool(
    name_override="get_support_ticket",
    description_override="Read a support ticket from the configured read-only ticketing connector.",
)
async def get_support_ticket(
    context: RunContextWrapper[EnterpriseAgentChatContext], ticket_key: str
) -> str:
    _, identity, store = _runtime(context)
    try:
        result = await _gateway(store).read_ticket(identity, ticket_key)
    except ConnectorError as exc:
        return _json(exc.as_dict())
    if result.get("status") == "ok":
        context.context.state.ticket_id = str(result.get("ticket_key") or "") or None
        context.context.state.ticket_status = result.get("ticket_status")
    return _json({**result, "source": "ticketing"})


@function_tool(
    name_override="open_billing_case",
    description_override="Generate a draft billing review for human review; never writes to the billing system.",
)
async def open_billing_case(
    context: RunContextWrapper[EnterpriseAgentChatContext],
    affected_period: str,
    reason: str,
) -> str:
    ctx = context.context.state
    chat_context, identity, store = _runtime(context)
    ctx.human_approval_required = True
    draft = store.create_action_draft(
        identity,
        thread_id=chat_context.thread.id,
        action_type="open_billing_case",
        parameters={"affected_period": affected_period, "reason": reason},
    )
    METRICS.increment(
        "enterprise_agent_action_drafts_total",
        action="open_billing_case",
        status="draft",
    )
    return _json(
        {
            "created": False,
            "draft_created": True,
            "draft_id": draft["id"],
            "approval_id": draft["id"],
            "status": "draft",
            "execution_mode": "draft_only",
        }
    )


@function_tool(
    name_override="lookup_security_compliance",
    description_override="Lookup approved security and compliance statements with source IDs.",
)
async def lookup_security_compliance(
    context: RunContextWrapper[EnterpriseAgentChatContext], topic: str
) -> str:
    chat_context, identity, store = _runtime(context)
    if hasattr(store, "search_knowledge"):
        matches = store.search_knowledge(identity, topic, category="compliance")
    else:
        normalized = topic.lower().replace(" ", "")
        key = next(
            (
                item
                for item in COMPLIANCE_LIBRARY
                if item.replace(" ", "") in normalized
            ),
            None,
        )
        matches = [COMPLIANCE_LIBRARY[key]] if key else []
    if not matches:
        gap = store.create_knowledge_gap(
            identity,
            topic,
            source="compliance_agent",
            thread_id=chat_context.thread.id,
        )
        return _json(
            {
                "status": "insufficient_evidence",
                "results": [],
                "knowledge_gap": True,
                "knowledge_gap_id": gap["id"],
                "recommended_action": "human_compliance_review",
            }
        )
    ctx = context.context.state
    ctx.compliance_topics = list(dict.fromkeys(ctx.compliance_topics + [topic]))
    refs = [item.get("document_id", item.get("id", "")) for item in matches]
    ctx.source_refs = list(dict.fromkeys(ctx.source_refs + refs))
    return _json(
        {
            "status": "grounded",
            "topic": topic,
            "results": matches,
            "qualification": "Confirm contract-specific terms with a human specialist.",
        }
    )


@function_tool(
    name_override="request_human_escalation",
    description_override="Create a human handoff request for incidents, commercial commitments, or unresolved risk.",
)
async def request_human_escalation(
    context: RunContextWrapper[EnterpriseAgentChatContext], reason: str, priority: str = "normal"
) -> str:
    ctx = context.context.state
    ctx.escalation_required = True
    chat_context, identity, store = _runtime(context)
    escalation = store.create_escalation(
        identity,
        thread_id=chat_context.thread.id,
        reason=reason,
        priority=priority,
    )
    METRICS.increment("enterprise_agent_human_escalations_total", priority=priority)
    return _json({**escalation, "reason": reason})
