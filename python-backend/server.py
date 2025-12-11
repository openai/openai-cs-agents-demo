from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
import asyncio
import json
from typing import Any, AsyncIterator, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel

from agents import (
    Handoff,
    HandoffOutputItem,
    InputGuardrailTripwireTriggered,
    ItemHelpers,
    MessageOutputItem,
    Runner,
    ToolCallItem,
    ToolCallOutputItem,
)
from agents.exceptions import MaxTurnsExceeded
from chatkit.agents import stream_agent_response
from chatkit.server import ChatKitServer
from chatkit.types import (
    Action,
    AssistantMessageContent,
    AssistantMessageItem,
    ClientEffectEvent,
    ThreadItemDoneEvent,
    ThreadMetadata,
    ThreadStreamEvent,
    UserMessageItem,
    WidgetItem,
    ProgressUpdateEvent,
)
from chatkit.store import NotFoundError

from airline.context import AirlineAgentChatContext, AirlineAgentContext, create_initial_context, public_context
from airline.agents import (
    booking_cancellation_agent,
    faq_agent,
    flight_information_agent,
    refunds_compensation_agent,
    seat_special_services_agent,
    triage_agent,
)
from memory_store import MemoryStore


class AgentEvent(BaseModel):
    id: str
    type: str
    agent: str
    content: str
    metadata: Optional[Dict[str, Any]] = None
    timestamp: Optional[float] = None


class GuardrailCheck(BaseModel):
    id: str
    name: str
    input: str
    reasoning: str
    passed: bool
    timestamp: float


def _get_agent_by_name(name: str):
    """Return the agent object by name."""
    agents = {
        triage_agent.name: triage_agent,
        faq_agent.name: faq_agent,
        seat_special_services_agent.name: seat_special_services_agent,
        flight_information_agent.name: flight_information_agent,
        booking_cancellation_agent.name: booking_cancellation_agent,
        refunds_compensation_agent.name: refunds_compensation_agent,
    }
    return agents.get(name, triage_agent)


def _get_guardrail_name(g) -> str:
    """Extract a friendly guardrail name."""
    name_attr = getattr(g, "name", None)
    if isinstance(name_attr, str) and name_attr:
        return name_attr
    guard_fn = getattr(g, "guardrail_function", None)
    if guard_fn is not None and hasattr(guard_fn, "__name__"):
        return guard_fn.__name__.replace("_", " ").title()
    fn_name = getattr(g, "__name__", None)
    if isinstance(fn_name, str) and fn_name:
        return fn_name.replace("_", " ").title()
    return str(g)


def _build_agents_list() -> List[Dict[str, Any]]:
    """Build a list of all available agents and their metadata."""

    def make_agent_dict(agent):
        return {
            "name": agent.name,
            "description": getattr(agent, "handoff_description", ""),
            "handoffs": [getattr(h, "agent_name", getattr(h, "name", "")) for h in getattr(agent, "handoffs", [])],
            "tools": [getattr(t, "name", getattr(t, "__name__", "")) for t in getattr(agent, "tools", [])],
            "input_guardrails": [_get_guardrail_name(g) for g in getattr(agent, "input_guardrails", [])],
        }

    return [
        make_agent_dict(triage_agent),
        make_agent_dict(faq_agent),
        make_agent_dict(seat_special_services_agent),
        make_agent_dict(flight_information_agent),
        make_agent_dict(booking_cancellation_agent),
        make_agent_dict(refunds_compensation_agent),
    ]


def _user_message_to_text(message: UserMessageItem) -> str:
    parts: List[str] = []
    for part in message.content:
        text = getattr(part, "text", "")
        if isinstance(text, str):
            parts.append(text)
    return "".join(parts)


def _parse_tool_args(raw_args: Any) -> Any:
    if isinstance(raw_args, str):
        try:
            import json

            return json.loads(raw_args)
        except Exception:
            return raw_args
    return raw_args


@dataclass
class ConversationState:
    input_items: List[Any] = field(default_factory=list)
    context: AirlineAgentContext = field(default_factory=create_initial_context)
    current_agent_name: str = triage_agent.name
    events: List[AgentEvent] = field(default_factory=list)
    guardrails: List[GuardrailCheck] = field(default_factory=list)


class AirlineServer(ChatKitServer[dict[str, Any]]):
    def __init__(self) -> None:
        self.store = MemoryStore()
        super().__init__(self.store)
        self._state: Dict[str, ConversationState] = {}
        self._listeners: Dict[str, list[asyncio.Queue]] = {}
        self._last_event_index: Dict[str, int] = {}
        self._last_snapshot: Dict[str, str] = {}

    def _state_for_thread(self, thread_id: str) -> ConversationState:
        if thread_id not in self._state:
            self._state[thread_id] = ConversationState()
        return self._state[thread_id]

    async def _ensure_thread(
        self, thread_id: Optional[str], context: dict[str, Any]
    ) -> ThreadMetadata:
        if thread_id:
            try:
                return await self.store.load_thread(thread_id, context)
            except NotFoundError:
                pass
        new_thread = ThreadMetadata(id=self.store.generate_thread_id(context), created_at=datetime.now())
        await self.store.save_thread(new_thread, context)
        self._state_for_thread(new_thread.id)
        return new_thread

    async def ensure_thread(self, thread_id: Optional[str], context: dict[str, Any]) -> ThreadMetadata:
        """Public wrapper to ensure a thread exists."""
        return await self._ensure_thread(thread_id, context)

    def _record_guardrails(
        self,
        agent_name: str,
        input_text: str,
        guardrail_results: List[Any],
    ) -> List[GuardrailCheck]:
        checks: List[GuardrailCheck] = []
        timestamp = time.time() * 1000
        agent = _get_agent_by_name(agent_name)
        for guardrail in getattr(agent, "input_guardrails", []):
            result = next((r for r in guardrail_results if r.guardrail == guardrail), None)
            reasoning = ""
            passed = True
            if result:
                info = getattr(result.output, "output_info", None)
                reasoning = getattr(info, "reasoning", "") or reasoning
                passed = not result.output.tripwire_triggered
            checks.append(
                GuardrailCheck(
                    id=uuid4().hex,
                    name=_get_guardrail_name(guardrail),
                    input=input_text,
                    reasoning=reasoning,
                    passed=passed,
                    timestamp=timestamp,
                )
            )
        return checks

    @staticmethod
    def _truncate(val: Any, limit: int = 200) -> Any:
        if isinstance(val, str) and len(val) > limit:
            return val[:limit] + "…"
        return val

    async def _broadcast_delta(self, thread: ThreadMetadata, delta_events: list[AgentEvent]) -> None:
        """Send a delta-only payload (used for transient progress updates)."""
        listeners = self._listeners.get(thread.id, [])
        if not listeners:
            return
        payload = json.dumps({"events_delta": [e.model_dump() for e in delta_events]}, default=str)
        for q in list(listeners):
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                pass

    def _record_events(
        self,
        run_items: List[Any],
        current_agent_name: str,
        thread_id: str,
    ) -> (List[AgentEvent], str):
        events: List[AgentEvent] = []
        active_agent = current_agent_name
        for item in run_items:
            now_ms = time.time() * 1000
            if isinstance(item, MessageOutputItem):
                text = self._truncate(ItemHelpers.text_message_output(item))
                events.append(
                    AgentEvent(
                        id=uuid4().hex,
                        type="message",
                        agent=item.agent.name,
                        content=text,
                        timestamp=now_ms,
                    )
                )
            elif isinstance(item, HandoffOutputItem):
                events.append(
                    AgentEvent(
                        id=uuid4().hex,
                        type="handoff",
                        agent=item.source_agent.name,
                        content=f"{item.source_agent.name} -> {item.target_agent.name}",
                        metadata={"source_agent": item.source_agent.name, "target_agent": item.target_agent.name},
                        timestamp=now_ms,
                    )
                )

                from_agent = item.source_agent
                to_agent = item.target_agent
                ho = next(
                    (
                        h
                        for h in getattr(from_agent, "handoffs", [])
                        if isinstance(h, Handoff) and getattr(h, "agent_name", None) == to_agent.name
                    ),
                    None,
                )
                if ho:
                    fn = ho.on_invoke_handoff
                    fv = fn.__code__.co_freevars
                    cl = fn.__closure__ or []
                    if "on_handoff" in fv:
                        idx = fv.index("on_handoff")
                        if idx < len(cl) and cl[idx].cell_contents:
                            cb = cl[idx].cell_contents
                            cb_name = getattr(cb, "__name__", repr(cb))
                            events.append(
                                AgentEvent(
                                    id=uuid4().hex,
                                    type="tool_call",
                                    agent=to_agent.name,
                                    content=cb_name,
                                    timestamp=now_ms,
                                )
                            )

                active_agent = to_agent.name
            elif isinstance(item, ToolCallItem):
                tool_name = getattr(item.raw_item, "name", None)
                raw_args = getattr(item.raw_item, "arguments", None)
                ev = AgentEvent(
                    id=uuid4().hex,
                    type="tool_call",
                    agent=item.agent.name,
                    content=self._truncate(tool_name or ""),
                    metadata={"tool_args": self._truncate(_parse_tool_args(raw_args))},
                    timestamp=now_ms,
                )
                events.append(ev)
            elif isinstance(item, ToolCallOutputItem):
                ev = AgentEvent(
                    id=uuid4().hex,
                    type="tool_output",
                    agent=item.agent.name,
                    content=self._truncate(str(item.output)),
                    metadata={"tool_result": self._truncate(item.output)},
                    timestamp=now_ms,
                )
                events.append(ev)

        return events, active_agent

    async def respond(
        self,
        thread: ThreadMetadata,
        input_user_message: UserMessageItem | None,
        context: dict[str, Any],
    ) -> AsyncIterator[ThreadStreamEvent]:
        state = self._state_for_thread(thread.id)
        user_text = ""
        if input_user_message is not None:
            user_text = _user_message_to_text(input_user_message)
            state.input_items.append({"content": user_text, "role": "user"})

        previous_context = public_context(state.context)
        chat_context = AirlineAgentChatContext(
            thread=thread,
            store=self.store,
            request_context=context,
            state=state.context,
        )
        streamed_items_seen = 0

        # Tell the client which thread to bind runner updates to before streaming starts.
        yield ClientEffectEvent(name="runner_bind_thread", data={"thread_id": thread.id, "ts": time.time()})

        try:
            result = Runner.run_streamed(
                _get_agent_by_name(state.current_agent_name),
                state.input_items,
                context=chat_context,
            )
            async for event in stream_agent_response(chat_context, result):
                if isinstance(event, ProgressUpdateEvent) or getattr(event, "type", "") == "progress_update_event":
                    # Ignore progress updates for the Runner panel; ChatKit will handle them separately.
                    continue
                # If this is a run-item event, convert and broadcast immediately.
                if hasattr(event, "item"):
                    try:
                        run_item = getattr(event, "item")
                        new_events, active_agent = self._record_events(
                            [run_item], state.current_agent_name, thread.id
                        )
                        if new_events:
                            state.events.extend(new_events)
                            state.current_agent_name = active_agent
                            await self._broadcast_state(thread, context)
                            yield ClientEffectEvent(
                                name="runner_state_update",
                                data={"thread_id": thread.id, "ts": time.time()},
                            )
                            yield ClientEffectEvent(
                                name="runner_event_delta",
                                data={
                                    "thread_id": thread.id,
                                    "ts": time.time(),
                                    "events": [e.model_dump() for e in new_events],
                                },
                            )
                    except Exception as err:
                        pass
                yield event
                new_items = result.new_items[streamed_items_seen:]
                if new_items:
                    new_events, active_agent = self._record_events(
                        new_items, state.current_agent_name, thread.id
                    )
                    state.events.extend(new_events)
                    state.current_agent_name = active_agent
                    streamed_items_seen += len(new_items)
                    await self._broadcast_state(thread, context)
                    yield ClientEffectEvent(
                        name="runner_state_update",
                        data={"thread_id": thread.id, "ts": time.time()},
                    )
                    yield ClientEffectEvent(
                        name="runner_event_delta",
                        data={
                            "thread_id": thread.id,
                            "ts": time.time(),
                            "events": [e.model_dump() for e in new_events],
                        },
                    )
        except MaxTurnsExceeded:
            await self._broadcast_state(thread, context)
        except InputGuardrailTripwireTriggered as exc:
            failed_guardrail = exc.guardrail_result.guardrail
            gr_output = exc.guardrail_result.output.output_info
            reasoning = getattr(gr_output, "reasoning", "")
            timestamp = time.time() * 1000
            checks: List[GuardrailCheck] = []
            for guardrail in _get_agent_by_name(state.current_agent_name).input_guardrails:
                checks.append(
                    GuardrailCheck(
                        id=uuid4().hex,
                        name=_get_guardrail_name(guardrail),
                        input=user_text,
                        reasoning=reasoning if guardrail == failed_guardrail else "",
                        passed=guardrail != failed_guardrail,
                        timestamp=timestamp,
                    )
                )
            state.guardrails = checks
            refusal = "Sorry, I can only answer questions related to airline travel."
            state.input_items.append({"role": "assistant", "content": refusal})
            yield ThreadItemDoneEvent(
                item=AssistantMessageItem(
                    id=self.store.generate_item_id("message", thread, context),
                    thread_id=thread.id,
                    created_at=datetime.now(),
                    content=[AssistantMessageContent(text=refusal)],
                )
            )
            return
        state.input_items = result.to_input_list()
        remaining_items = result.new_items[streamed_items_seen:]
        new_events, active_agent = self._record_events(remaining_items, state.current_agent_name, thread.id)
        state.events.extend(new_events)
        final_agent_name = active_agent
        try:
            final_agent_name = result.last_agent.name
        except Exception:
            pass
        state.current_agent_name = final_agent_name
        state.guardrails = self._record_guardrails(
            agent_name=state.current_agent_name,
            input_text=user_text,
            guardrail_results=result.input_guardrail_results,
        )

        new_context = public_context(state.context)
        changes = {k: new_context[k] for k in new_context if previous_context.get(k) != new_context[k]}
        if changes:
            state.events.append(
                AgentEvent(
                    id=uuid4().hex,
                    type="context_update",
                    agent=state.current_agent_name,
                    content="",
                    metadata={"changes": changes},
                    timestamp=time.time() * 1000,
                )
            )
        await self._broadcast_state(thread, context)
        yield ClientEffectEvent(
            name="runner_state_update",
            data={"thread_id": thread.id, "ts": time.time()},
        )
        if new_events:
            yield ClientEffectEvent(
                name="runner_event_delta",
                data={
                    "thread_id": thread.id,
                    "ts": time.time(),
                    "events": [e.model_dump() for e in new_events],
                },
            )

    async def action(
        self,
        thread: ThreadMetadata,
        action: Action[str, Any],
        sender: WidgetItem | None,
        context: dict[str, Any],
    ) -> AsyncIterator[ThreadStreamEvent]:
        # No client-handled actions in this demo.
        if False:
            yield

    async def snapshot(self, thread_id: Optional[str], context: dict[str, Any]) -> Dict[str, Any]:
        thread = await self._ensure_thread(thread_id, context)
        state = self._state_for_thread(thread.id)
        return {
            "thread_id": thread.id,
            "current_agent": state.current_agent_name,
            "context": public_context(state.context),
            "agents": _build_agents_list(),
            "events": [e.model_dump() for e in state.events],
            "guardrails": [g.model_dump() for g in state.guardrails],
        }

    # -- Streaming state updates to UI listeners ---------------------------------
    def _register_listener(self, thread_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._listeners.setdefault(thread_id, []).append(q)
        # Push last snapshot if available so late listeners get current state immediately.
        last = self._last_snapshot.get(thread_id)
        if last:
            try:
                q.put_nowait(last)
            except asyncio.QueueFull:
                pass
        return q

    def register_listener(self, thread_id: str) -> asyncio.Queue:
        """Public wrapper for listener registration."""
        return self._register_listener(thread_id)

    def _unregister_listener(self, thread_id: str, queue: asyncio.Queue) -> None:
        listeners = self._listeners.get(thread_id, [])
        if queue in listeners:
            listeners.remove(queue)
        if not listeners and thread_id in self._listeners:
            self._listeners.pop(thread_id, None)

    def unregister_listener(self, thread_id: str, queue: asyncio.Queue) -> None:
        """Public wrapper for listener cleanup."""
        self._unregister_listener(thread_id, queue)

    async def _broadcast_state(self, thread: ThreadMetadata, context: dict[str, Any]) -> None:
        listeners = self._listeners.get(thread.id, [])
        if not listeners:
            return
        snap = await self.snapshot(thread.id, context)
        # Compute delta of new events since last broadcast to reduce payloads
        last_idx = self._last_event_index.get(thread.id, 0)
        total_events = len(snap.get("events", []))
        delta = snap.get("events", [])[last_idx:] if total_events >= last_idx else snap.get("events", [])
        self._last_event_index[thread.id] = total_events
        payload_obj = {
            **snap,
            "events_delta": delta,
        }
        payload = json.dumps(payload_obj, default=str)
        self._last_snapshot[thread.id] = payload
        for q in list(listeners):
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                pass
