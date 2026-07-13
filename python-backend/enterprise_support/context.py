from __future__ import annotations

from chatkit.agents import AgentContext
from pydantic import BaseModel, Field


class EnterpriseAgentContext(BaseModel):
    """Shared business context carried across specialist handoffs."""

    customer_name: str | None = None
    company_name: str | None = None
    account_id: str | None = None
    tenant_id: str | None = None
    plan: str | None = None
    deployment_environment: str | None = None
    product_area: str | None = None
    issue_summary: str | None = None
    severity: str | None = None
    ticket_id: str | None = None
    ticket_status: str | None = None
    opportunity_id: str | None = None
    billing_case_id: str | None = None
    compliance_topics: list[str] = Field(default_factory=list)
    recommended_architecture: str | None = None
    escalation_required: bool = False
    human_approval_required: bool = False
    source_refs: list[str] = Field(default_factory=list)
    verified_identity: bool = False
    internal_notes: list[str] = Field(default_factory=list)


class EnterpriseAgentChatContext(AgentContext[dict]):
    """ChatKit context wrapper containing the persisted business state."""

    state: EnterpriseAgentContext


def create_initial_context() -> EnterpriseAgentContext:
    return EnterpriseAgentContext()


def public_context(ctx: EnterpriseAgentContext) -> dict:
    """Return the customer-safe subset displayed in the orchestration panel."""

    data = ctx.model_dump()
    for key in ("tenant_id", "verified_identity", "internal_notes", "source_refs"):
        data.pop(key, None)
    if not data.get("compliance_topics"):
        data.pop("compliance_topics", None)
    return data

