from __future__ import annotations as _annotations

import random
import string
from copy import deepcopy

from agents import RunContextWrapper, function_tool
from chatkit.types import ProgressUpdateEvent

from .context import AirlineAgentChatContext
from .demo_data import active_itinerary, apply_itinerary_defaults, get_itinerary_for_flight


@function_tool(
    name_override="faq_lookup_tool", description_override="Lookup frequently asked questions."
)
async def faq_lookup_tool(question: str) -> str:
    """Lookup answers to frequently asked questions."""
    q = question.lower()
    if "bag" in q or "baggage" in q:
        return (
            "You are allowed to bring one bag on the plane. "
            "It must be under 50 pounds and 22 inches x 14 inches x 9 inches. "
            "If a bag is delayed or missing, file a baggage claim and we will track it for delivery."
        )
    if "compensation" in q or "delay" in q or "voucher" in q:
        return (
            "For lengthy delays we provide duty-of-care: hotel and meal vouchers plus ground transport where needed. "
            "If the delay is over 3 hours or causes a missed connection, we also open a compensation case and can offer miles or travel credit. "
            "A Refunds & Compensation agent can submit the case and share the voucher details with you."
        )
    elif "seats" in q or "plane" in q:
        return (
            "There are 120 seats on the plane. "
            "There are 22 business class seats and 98 economy seats. "
            "Exit rows are rows 4 and 16. "
            "Rows 5-8 are Economy Plus, with extra legroom."
        )
    elif "wifi" in q:
        return "We have free wifi on the plane, join Airline-Wifi"
    return "I'm sorry, I don't know the answer to that question."


@function_tool(
    name_override="get_trip_details",
    description_override="Infer the disrupted Paris->New York->Austin trip from user text and hydrate context.",
)
async def get_trip_details(
    context: RunContextWrapper[AirlineAgentChatContext], message: str
) -> str:
    """
    If the user mentions Paris, New York, or Austin, hydrate the context with the disrupted mock itinerary.
    Otherwise, hydrate the on-time mock itinerary. Returns the detected flight and confirmation.
    """
    text = message.lower()
    keywords = ["paris", "new york", "austin"]
    scenario_key = "disrupted" if any(k in text for k in keywords) else "on_time"
    apply_itinerary_defaults(context.context.state, scenario_key=scenario_key)
    ctx = context.context.state
    if scenario_key == "disrupted":
        ctx.origin = ctx.origin or "Paris (CDG)"
        ctx.destination = ctx.destination or "Austin (AUS)"
    segments = ctx.itinerary or []
    segment_summaries = []
    for seg in segments:
        segment_summaries.append(
            f"{seg.get('flight_number')} {seg.get('origin')} -> {seg.get('destination')} "
            f"status: {seg.get('status')}"
        )
    summary = "; ".join(segment_summaries) if segment_summaries else "No segment details available"
    return (
        f"Hydrated {scenario_key} itinerary: flight {ctx.flight_number}, confirmation "
        f"{ctx.confirmation_number}, origin {ctx.origin}, destination {ctx.destination}. {summary}"
    )


@function_tool
async def update_seat(
    context: RunContextWrapper[AirlineAgentChatContext], confirmation_number: str, new_seat: str
) -> str:
    """Update the seat for a given confirmation number."""
    apply_itinerary_defaults(context.context.state)
    context.context.state.confirmation_number = confirmation_number
    context.context.state.seat_number = new_seat
    assert context.context.state.flight_number is not None, "Flight number is required"
    return f"Updated seat to {new_seat} for confirmation number {confirmation_number}"


@function_tool(
    name_override="flight_status_tool",
    description_override="Lookup status for a flight."
)
async def flight_status_tool(
    context: RunContextWrapper[AirlineAgentChatContext], flight_number: str
) -> str:
    """Lookup the status for a flight using mock itineraries."""
    await context.context.stream(ProgressUpdateEvent(text=f"Checking status for {flight_number}..."))
    ctx_state = context.context.state
    ctx_state.flight_number = flight_number
    match = get_itinerary_for_flight(flight_number)
    if match:
        scenario_key, itinerary = match
        apply_itinerary_defaults(ctx_state, scenario_key=scenario_key)
        segments = itinerary.get("segments", [])
        rebook_options = itinerary.get("rebook_options", [])
        segment = next(
            (seg for seg in segments if seg.get("flight_number", "").lower() == flight_number.lower()),
            None,
        )
        if segment:
            route = f"{segment.get('origin', 'Unknown')} to {segment.get('destination', 'Unknown')}"
            details = [
                f"Flight {flight_number} ({route})",
                f"Status: {segment.get('status', 'On time')}",
            ]
            if segment.get("gate"):
                details.append(f"Gate: {segment['gate']}")
            if segment.get("departure") and segment.get("arrival"):
                details.append(f"Scheduled {segment['departure']} -> {segment['arrival']}")
            if scenario_key == "disrupted" and segment.get("flight_number") == "PA441":
                details.append("This delay will cause a missed connection to NY802. Reaccommodation is recommended.")
            await context.context.stream(
                ProgressUpdateEvent(text=f"Found status for flight {flight_number}")
            )
            return " | ".join(details)
        replacement = next(
            (
                seg
                for seg in rebook_options
                if seg.get("flight_number", "").lower() == flight_number.lower()
            ),
            None,
        )
        if replacement:
            route = f"{replacement.get('origin', 'Unknown')} to {replacement.get('destination', 'Unknown')}"
            seat = replacement.get("seat", "auto-assign")
            await context.context.stream(
                ProgressUpdateEvent(text=f"Found alternate flight {flight_number}")
            )
            return (
                f"Replacement flight {flight_number} ({route}) is available. "
                f"Departure {replacement.get('departure')} arriving {replacement.get('arrival')}. Seat {seat} held."
            )
    await context.context.stream(ProgressUpdateEvent(text=f"No disruptions found for {flight_number}"))
    return f"Flight {flight_number} is on time and scheduled to depart at gate A10."


@function_tool(
    name_override="baggage_tool",
    description_override="Lookup baggage allowance and fees."
)
async def baggage_tool(query: str) -> str:
    """Lookup baggage allowance and fees."""
    q = query.lower()
    if "fee" in q:
        return "Overweight bag fee is $75."
    if "allowance" in q:
        return "One carry-on and one checked bag (up to 50 lbs) are included."
    if "missing" in q or "lost" in q:
        return "If a bag is missing, file a baggage claim at the airport or with the Baggage Agent so we can track and deliver it."
    return "Please provide details about your baggage inquiry."


@function_tool(
    name_override="get_matching_flights",
    description_override="Find replacement flights when a segment is delayed or cancelled."
)
async def get_matching_flights(
    context: RunContextWrapper[AirlineAgentChatContext],
    origin: str | None = None,
    destination: str | None = None,
) -> str:
    """Return mock matching flights for a disrupted itinerary."""
    await context.context.stream(ProgressUpdateEvent(text="Scanning for matching flights..."))
    ctx_state = context.context.state
    scenario_key, itinerary = active_itinerary(ctx_state)
    apply_itinerary_defaults(ctx_state, scenario_key=scenario_key)
    options = itinerary.get("rebook_options", [])
    if not options:
        await context.context.stream(ProgressUpdateEvent(text="No alternates needed — trip on time"))
        return "All flights are operating on time. No alternate flights are needed."
    filtered = [
        opt
        for opt in options
        if (origin is None or origin.lower() in opt.get("origin", "").lower())
        and (destination is None or destination.lower() in opt.get("destination", "").lower())
    ]
    final_options = filtered or options
    await context.context.stream(
        ProgressUpdateEvent(text=f"Found {len(final_options)} matching flight option(s)")
    )
    lines = []
    for opt in final_options:
        lines.append(
            f"{opt.get('flight_number')} {opt.get('origin')} -> {opt.get('destination')} "
            f"dep {opt.get('departure')} arr {opt.get('arrival')} | seat {opt.get('seat', 'auto-assign')} | {opt.get('note', '')}"
        )
    if scenario_key == "disrupted":
        lines.append("These options arrive in Austin the next day. Overnight hotel and meals are covered.")
    ctx_state.itinerary = ctx_state.itinerary or deepcopy(itinerary.get("segments", []))
    return "Matching flights:\n" + "\n".join(lines)


@function_tool(
    name_override="book_new_flight",
    description_override="Book a new or replacement flight and auto-assign a seat."
)
async def book_new_flight(
    context: RunContextWrapper[AirlineAgentChatContext], flight_number: str | None = None
) -> str:
    """Book a replacement flight using mock inventory and update context."""
    await context.context.stream(ProgressUpdateEvent(text="Booking replacement flight..."))
    ctx_state = context.context.state
    scenario_key, itinerary = active_itinerary(ctx_state)
    apply_itinerary_defaults(ctx_state, scenario_key=scenario_key)
    options = itinerary.get("rebook_options", [])
    selection = None
    if flight_number:
        selection = next(
            (opt for opt in options if opt.get("flight_number", "").lower() == flight_number.lower()),
            None,
        )
    if selection is None and options:
        selection = options[0]
    if selection is None:
        seat = ctx_state.seat_number or "auto-assign"
        confirmation = ctx_state.confirmation_number or "".join(
            random.choices(string.ascii_uppercase + string.digits, k=6)
        )
        ctx_state.confirmation_number = confirmation
        await context.context.stream(ProgressUpdateEvent(text="Booked placeholder flight"))
        return (
            f"Booked flight {flight_number or 'TBD'} with confirmation {confirmation}. "
            f"Seat assignment: {seat}."
        )
    ctx_state.flight_number = selection.get("flight_number")
    ctx_state.seat_number = selection.get("seat") or ctx_state.seat_number or "auto-assign"
    ctx_state.itinerary = ctx_state.itinerary or deepcopy(itinerary.get("segments", []))
    updated_itinerary = [
        seg
        for seg in ctx_state.itinerary
        if not (
            scenario_key == "disrupted"
            and seg.get("origin", "").startswith("New York")
            and seg.get("destination", "").startswith("Austin")
        )
    ]
    updated_itinerary.append(
        {
            "flight_number": selection["flight_number"],
            "origin": selection.get("origin", ""),
            "destination": selection.get("destination", ""),
            "departure": selection.get("departure", ""),
            "arrival": selection.get("arrival", ""),
            "status": "Confirmed replacement flight",
            "gate": "TBD",
        }
    )
    ctx_state.itinerary = updated_itinerary
    confirmation = ctx_state.confirmation_number or "".join(
        random.choices(string.ascii_uppercase + string.digits, k=6)
    )
    ctx_state.confirmation_number = confirmation
    await context.context.stream(
        ProgressUpdateEvent(
            text=f"Rebooked to {selection['flight_number']} with seat {ctx_state.seat_number}",
        )
    )
    return (
        f"Rebooked to {selection['flight_number']} from {selection.get('origin')} to {selection.get('destination')}. "
        f"Departure {selection.get('departure')}, arrival {selection.get('arrival')} (next day arrival in Austin). "
        f"Seat assigned: {ctx_state.seat_number}. Confirmation {confirmation}."
    )


@function_tool(
    name_override="assign_special_service_seat",
    description_override="Assign front row or special service seating for medical needs."
)
async def assign_special_service_seat(
    context: RunContextWrapper[AirlineAgentChatContext], seat_request: str = "front row for medical needs"
) -> str:
    """Assign a special service seat and record the request."""
    ctx_state = context.context.state
    apply_itinerary_defaults(ctx_state)
    preferred_seat = "1A" if "front" in seat_request.lower() else "2A"
    ctx_state.seat_number = preferred_seat
    ctx_state.special_service_note = seat_request
    confirmation = ctx_state.confirmation_number or "".join(
        random.choices(string.ascii_uppercase + string.digits, k=6)
    )
    ctx_state.confirmation_number = confirmation
    return (
        f"Secured {seat_request} seat {preferred_seat} on flight {ctx_state.flight_number or 'upcoming segment'}. "
        f"Confirmation {confirmation} noted with special service flag."
    )


@function_tool(
    name_override="issue_compensation",
    description_override="Create a compensation case and issue hotel/meal vouchers."
)
async def issue_compensation(
    context: RunContextWrapper[AirlineAgentChatContext], reason: str = "Delay causing missed connection"
) -> str:
    """Open a compensation case and attach vouchers."""
    await context.context.stream(ProgressUpdateEvent(text="Opening compensation case..."))
    ctx_state = context.context.state
    scenario_key, itinerary = active_itinerary(ctx_state)
    apply_itinerary_defaults(ctx_state, scenario_key=scenario_key)
    case_id = ctx_state.compensation_case_id or f"CMP-{random.randint(1000, 9999)}"
    ctx_state.compensation_case_id = case_id
    voucher_values = list(itinerary.get("vouchers", {}).values())
    if voucher_values:
        ctx_state.vouchers = voucher_values
    else:
        ctx_state.vouchers = ctx_state.vouchers or []
    vouchers_text = "; ".join(ctx_state.vouchers) if ctx_state.vouchers else "Documented compensation with no vouchers required."
    await context.context.stream(ProgressUpdateEvent(text=f"Issued vouchers for case {case_id}"))
    return (
        f"Opened compensation case {case_id} for: {reason}. "
        f"Issued: {vouchers_text}. Keep receipts for any hotel or meal costs and attach them to this case."
    )


@function_tool(
    name_override="display_seat_map",
    description_override="Display an interactive seat map to the customer so they can choose a new seat."
)
async def display_seat_map(
    context: RunContextWrapper[AirlineAgentChatContext]
) -> str:
    """Trigger the UI to show an interactive seat map to the customer."""
    # The returned string will be interpreted by the UI to open the seat selector.
    return "DISPLAY_SEAT_MAP"


@function_tool(
    name_override="cancel_flight",
    description_override="Cancel a flight."
)
async def cancel_flight(
    context: RunContextWrapper[AirlineAgentChatContext]
) -> str:
    """Cancel the flight in the context."""
    apply_itinerary_defaults(context.context.state)
    fn = context.context.state.flight_number
    assert fn is not None, "Flight number is required"
    confirmation = context.context.state.confirmation_number or "".join(
        random.choices(string.ascii_uppercase + string.digits, k=6)
    )
    context.context.state.confirmation_number = confirmation
    return f"Flight {fn} successfully cancelled for confirmation {confirmation}"
