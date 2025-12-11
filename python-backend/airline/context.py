from __future__ import annotations as _annotations

from chatkit.agents import AgentContext
from pydantic import BaseModel


class AirlineAgentContext(BaseModel):
    """Context for airline customer service agents."""

    passenger_name: str | None = None
    confirmation_number: str | None = None
    seat_number: str | None = None
    flight_number: str | None = None
    account_number: str | None = None  # Account number associated with the customer
    itinerary: list[dict[str, str]] | None = None  # Internal only (not surfaced to UI)
    baggage_claim_id: str | None = None  # Internal only (not surfaced to UI)
    compensation_case_id: str | None = None
    scenario: str | None = None
    vouchers: list[str] | None = None
    special_service_note: str | None = None
    origin: str | None = None
    destination: str | None = None


class AirlineAgentChatContext(AgentContext[dict]):
    """
    AgentContext wrapper used during ChatKit runs.
    Holds the persisted AirlineAgentContext in `state`.
    """

    state: AirlineAgentContext


def create_initial_context() -> AirlineAgentContext:
    """
    Factory for a new AirlineAgentContext.
    Starts empty; values are populated during the conversation.
    """
    ctx = AirlineAgentContext()
    return ctx


def public_context(ctx: AirlineAgentContext) -> dict:
    """
    Return a filtered view of the context for UI display.
    Hides internal fields like itinerary and baggage_claim_id, and only shows vouchers when granted.
    """
    data = ctx.model_dump()
    hidden_keys = {
        "itinerary",
        "baggage_claim_id",
        "compensation_case_id",
        "scenario",
    }
    for key in list(data.keys()):
        if key in hidden_keys:
            data.pop(key, None)
    # Only surface vouchers once granted
    if not data.get("vouchers"):
        data.pop("vouchers", None)
    return data
