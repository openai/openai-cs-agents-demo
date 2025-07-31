from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Import building blocks and built-ins from the current agent graph
from agents import (
    Agent,
    Handoff,
    InputGuardrailTripwireTriggered,
    ItemHelpers,
    MessageOutputItem,
    Runner,
    ToolCallItem,
    ToolCallOutputItem,
    handoff as handoff_helper,
)
from types import SimpleNamespace
from main import (
    # Context
    create_initial_context,
    # Tools
    faq_lookup_tool,
    display_seat_map,
    update_seat,
    flight_status_tool,
    cancel_flight,
    baggage_tool,
    # Guardrails
    relevance_guardrail,
    jailbreak_guardrail,
    # Instruction builders / hooks
    seat_booking_instructions,
    flight_status_instructions,
    cancellation_instructions,
    on_seat_booking_handoff,
    on_cancellation_handoff,
)

# ------------------------------------------------------------
# App + CORS
# ------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------
# Types used by API responses (unchanged)
# ------------------------------------------------------------
class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    message: str


class MessageResponse(BaseModel):
    content: str
    agent: str


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


class ChatResponse(BaseModel):
    conversation_id: str
    current_agent: str
    messages: List[MessageResponse]
    events: List[AgentEvent]
    context: Dict[str, Any]
    agents: List[Dict[str, Any]]
    guardrails: List[GuardrailCheck] = []


# ------------------------------------------------------------
# Conversation store (unchanged)
# ------------------------------------------------------------
class ConversationStore:
    def get(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        pass

    def save(self, conversation_id: str, state: Dict[str, Any]):
        pass


class InMemoryConversationStore(ConversationStore):
    _conversations: Dict[str, Dict[str, Any]] = {}

    def get(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        return self._conversations.get(conversation_id)

    def save(self, conversation_id: str, state: Dict[str, Any]):
        self._conversations[conversation_id] = state


conversation_store = InMemoryConversationStore()

# ------------------------------------------------------------
# Dynamic registry: load/save config and build Agent objects
# ------------------------------------------------------------
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "agents_config.json")

TOOL_MAP = {
    "faq_lookup_tool": faq_lookup_tool,
    "display_seat_map": display_seat_map,
    "update_seat": update_seat,
    "flight_status_tool": flight_status_tool,
    "cancel_flight": cancel_flight,
    "baggage_tool": baggage_tool,
}

HANDOFF_HOOKS = {
    "on_seat_booking_handoff": on_seat_booking_handoff,
    "on_cancellation_handoff": on_cancellation_handoff,
}

INSTRUCTION_BUILTINS = {
    "seat_booking_instructions": seat_booking_instructions,
    "flight_status_instructions": flight_status_instructions,
    "cancellation_instructions": cancellation_instructions,
}

GUARDRAILS_MAP = {
    "relevance_guardrail": relevance_guardrail,
    "jailbreak_guardrail": jailbreak_guardrail,
}


def default_config() -> Dict[str, Any]:
    """Default graph equivalent to the current hardcoded setup."""
    return {
        "primary_agent_name": "Triage Agent",
        "agents": [
            {
                "name": "Triage Agent",
                "description": "A triage agent that can delegate a customer's request to the appropriate agent.",
                "model": "gpt-4.1",
                "instructions": {
                    "mode": "custom",
                    "value": "You are a helpful triaging agent. You can use your tools to delegate questions to other appropriate agents.",
                },
                "tools": [],
                "input_guardrails": ["relevance_guardrail", "jailbreak_guardrail"],
                "handoffs": [
                    {"target": "Flight Status Agent"},
                    {"target": "Cancellation Agent", "on_handoff": "on_cancellation_handoff"},
                    {"target": "FAQ Agent"},
                    {"target": "Seat Booking Agent", "on_handoff": "on_seat_booking_handoff"},
                ],
            },
            {
                "name": "Flight Status Agent",
                "description": "An agent to provide flight status information.",
                "model": "gpt-4.1",
                "instructions": {"mode": "builtin", "builtin": "flight_status_instructions"},
                "tools": ["flight_status_tool"],
                "input_guardrails": ["relevance_guardrail", "jailbreak_guardrail"],
                "handoffs": [{"target": "Triage Agent"}],
            },
            {
                "name": "Cancellation Agent",
                "description": "An agent to cancel flights.",
                "model": "gpt-4.1",
                "instructions": {"mode": "builtin", "builtin": "cancellation_instructions"},
                "tools": ["cancel_flight"],
                "input_guardrails": ["relevance_guardrail", "jailbreak_guardrail"],
                "handoffs": [{"target": "Triage Agent"}],
            },
            {
                "name": "FAQ Agent",
                "description": "A helpful agent that can answer questions about the airline.",
                "model": "gpt-4.1",
                "instructions": {
                    "mode": "custom",
                    "value": "You are an FAQ agent. Use your faq_lookup_tool to answer the customer's last question.",
                },
                "tools": ["faq_lookup_tool"],
                "input_guardrails": ["relevance_guardrail", "jailbreak_guardrail"],
                "handoffs": [{"target": "Triage Agent"}],
            },
            {
                "name": "Seat Booking Agent",
                "description": "A helpful agent that can update a seat on a flight.",
                "model": "gpt-4.1",
                "instructions": {"mode": "builtin", "builtin": "seat_booking_instructions"},
                "tools": ["update_seat", "display_seat_map"],
                "input_guardrails": ["relevance_guardrail", "jailbreak_guardrail"],
                "handoffs": [{"target": "Triage Agent"}],
            },
        ],
    }


def load_config() -> Dict[str, Any]:
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("Failed to read config; using defaults: %s", e)
    cfg = default_config()
    save_config(cfg)
    return cfg


def save_config(cfg: Dict[str, Any]):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


class AgentsRegistry:
    def __init__(self):
        self.config: Dict[str, Any] = {}
        self.agents_by_name: Dict[str, Agent] = {}
        self.primary_agent_name: str = "Triage Agent"

    def rebuild(self, cfg: Dict[str, Any]):
        self.config = cfg
        self.primary_agent_name = cfg.get("primary_agent_name") or "Triage Agent"
        name_to_agent: Dict[str, Agent] = {}
        # First pass: create Agent objects without handoffs
        for a in cfg.get("agents", []):
            name = a["name"]
            desc = a.get("description", "")
            model = a.get("model", "gpt-4.1")
            instr = a.get("instructions", {"mode": "custom", "value": f"You are {name}."})
            instructions_value: Any
            if instr.get("mode") == "builtin":
                fn_name = instr.get("builtin", "")
                instructions_value = INSTRUCTION_BUILTINS.get(fn_name) or instr.get("value", f"You are {name}.")
            else:
                instructions_value = instr.get("value", f"You are {name}.")
            tools = [TOOL_MAP[t] for t in a.get("tools", []) if t in TOOL_MAP]
            guards = [GUARDRAILS_MAP[g] for g in a.get("input_guardrails", []) if g in GUARDRAILS_MAP]
            agent_obj = Agent(
                name=name,
                model=model,
                handoff_description=desc,
                instructions=instructions_value,
                tools=tools,
                input_guardrails=guards,
            )
            name_to_agent[name] = agent_obj
        # Second pass: wire handoffs
        for a in cfg.get("agents", []):
            src = name_to_agent[a["name"]]
            ho_list: List[Any] = []
            for ho in a.get("handoffs", []):
                tgt_name = ho.get("target")
                if not tgt_name or tgt_name not in name_to_agent:
                    continue
                cb = HANDOFF_HOOKS.get(ho.get("on_handoff")) if ho.get("on_handoff") else None
                ho_list.append(handoff_helper(agent=name_to_agent[tgt_name], on_handoff=cb))
            # Also allow returning to triage for non-triage
            src.handoffs = ho_list
        self.agents_by_name = name_to_agent

    def get(self, name: str) -> Agent:
        return self.agents_by_name.get(name) or self.agents_by_name.get(self.primary_agent_name)

    def list_agents(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for name, agent in self.agents_by_name.items():
            # Find config entry to list declared handoffs by name
            cfg_a = next((x for x in self.config.get("agents", []) if x.get("name") == name), None)
            handoffs = [h.get("target") for h in (cfg_a.get("handoffs", []) if cfg_a else [])]
            out.append(
                {
                    "name": agent.name,
                    "description": getattr(agent, "handoff_description", ""),
                    "handoffs": handoffs,
                    "tools": [getattr(t, "name", getattr(t, "__name__", "")) for t in getattr(agent, "tools", [])],
                    "input_guardrails": [
                        getattr(g, "name", getattr(getattr(g, "guardrail_function", None), "__name__", ""))
                        for g in getattr(agent, "input_guardrails", [])
                    ],
                }
            )
        return out


registry = AgentsRegistry()
registry.rebuild(load_config())

# ------------------------------------------------------------
# Utility helpers
# ------------------------------------------------------------

def _get_guardrail_name(g) -> str:
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


# ------------------------------------------------------------
# Config/whitelist endpoints
# ------------------------------------------------------------
@app.get("/agents-config")
def get_agents_config():
    return registry.config


@app.put("/agents-config")
def put_agents_config(cfg: Dict[str, Any]):
    # Basic validation: unique names
    names = [a.get("name") for a in cfg.get("agents", [])]
    if len(names) != len(set(names)):
        return {"ok": False, "error": "Agent names must be unique"}
    save_config(cfg)
    registry.rebuild(cfg)
    return {"ok": True, "config": registry.config}


@app.post("/agents-config/reset")
def reset_agents_config():
    cfg = default_config()
    save_config(cfg)
    registry.rebuild(cfg)
    return {"ok": True, "config": registry.config}


@app.get("/agents-config/whitelists")
def get_whitelists():
        return {
        "tools": sorted(list(TOOL_MAP.keys())),
        "handoff_hooks": sorted(list(HANDOFF_HOOKS.keys())),
        "builtin_instructions": sorted(list(INSTRUCTION_BUILTINS.keys())),
        "guardrails": sorted(list(GUARDRAILS_MAP.keys())),
    }


# Effective instructions preview (expand builtin instructions into text)
@app.get("/agents-config/effective")
def get_effective_instructions():
    cfg = registry.config
    out: List[Dict[str, str]] = []
    for a in cfg.get("agents", []):
        instr = a.get("instructions", {})
        text = ""
        try:
            if instr.get("mode") == "builtin":
                fn_name = instr.get("builtin")
                fn = INSTRUCTION_BUILTINS.get(fn_name)
                if fn:
                    # Build a lightweight wrapper with a default context
                    rcw = SimpleNamespace(context=create_initial_context())
                    preview_agent = Agent(name=a.get("name", "Agent"), model=a.get("model", "gpt-4.1"))
                    text = fn(rcw, preview_agent)
            else:
                text = instr.get("value", "")
        except Exception as e:
            text = f"(error rendering instructions: {e})"
        out.append({
            "name": a.get("name", "Agent"),
            "description": a.get("description", ""),
            "instructions": text,
        })
    return {"agents": out}


# ------------------------------------------------------------
# Chat endpoint using dynamic registry
# ------------------------------------------------------------
@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    # Initialize or retrieve conversation state
    is_new = not req.conversation_id or conversation_store.get(req.conversation_id) is None
    if is_new:
        conversation_id: str = uuid4().hex
        ctx = create_initial_context()
        current_agent_name = registry.primary_agent_name
        state: Dict[str, Any] = {
            "input_items": [],
            "context": ctx,
            "current_agent": current_agent_name,
        }
        if req.message.strip() == "":
            conversation_store.save(conversation_id, state)
            return ChatResponse(
                conversation_id=conversation_id,
                current_agent=current_agent_name,
                messages=[],
                events=[],
                context=ctx.model_dump(),
                agents=registry.list_agents(),
                guardrails=[],
            )
    else:
        conversation_id = req.conversation_id  # type: ignore
        state = conversation_store.get(conversation_id)

    current_agent = registry.get(state["current_agent"])  # type: ignore
    state["input_items"].append({"content": req.message, "role": "user"})
    old_context = state["context"].model_dump().copy()
    guardrail_checks: List[GuardrailCheck] = []

    try:
        result = await Runner.run(current_agent, state["input_items"], context=state["context"])
    except InputGuardrailTripwireTriggered as e:
        failed = e.guardrail_result.guardrail
        gr_output = e.guardrail_result.output.output_info
        gr_reasoning = getattr(gr_output, "reasoning", "")
        gr_input = req.message
        gr_timestamp = time.time() * 1000
        for g in current_agent.input_guardrails:
            guardrail_checks.append(
                GuardrailCheck(
                id=uuid4().hex,
                name=_get_guardrail_name(g),
                input=gr_input,
                reasoning=(gr_reasoning if g == failed else ""),
                passed=(g != failed),
                timestamp=gr_timestamp,
                )
            )
        refusal = "Sorry, I can only answer questions related to airline travel."
        state["input_items"].append({"role": "assistant", "content": refusal})
        return ChatResponse(
            conversation_id=conversation_id,
            current_agent=current_agent.name,
            messages=[MessageResponse(content=refusal, agent=current_agent.name)],
            events=[],
            context=state["context"].model_dump(),
            agents=registry.list_agents(),
            guardrails=guardrail_checks,
        )

    messages: List[MessageResponse] = []
    events: List[AgentEvent] = []

    for item in result.new_items:
        if isinstance(item, MessageOutputItem):
            text = ItemHelpers.text_message_output(item)
            messages.append(MessageResponse(content=text, agent=item.agent.name))
            events.append(AgentEvent(id=uuid4().hex, type="message", agent=item.agent.name, content=text))
        elif isinstance(item, HandoffOutputItem):
            events.append(
                AgentEvent(
                    id=uuid4().hex,
                    type="handoff",
                    agent=item.source_agent.name,
                    content=f"{item.source_agent.name} -> {item.target_agent.name}",
                    metadata={"source_agent": item.source_agent.name, "target_agent": item.target_agent.name},
                )
            )
            # detect on_handoff callback invocation for trace display
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
                            )
                        )
            current_agent = item.target_agent
        elif isinstance(item, ToolCallItem):
            tool_name = getattr(item.raw_item, "name", None)
            raw_args = getattr(item.raw_item, "arguments", None)
            tool_args: Any = raw_args
            if isinstance(raw_args, str):
                try:
                    tool_args = json.loads(raw_args)
                except Exception:
                    pass
            events.append(
                AgentEvent(
                    id=uuid4().hex,
                    type="tool_call",
                    agent=item.agent.name,
                    content=tool_name or "",
                    metadata={"tool_args": tool_args},
                )
            )
            if tool_name == "display_seat_map":
                messages.append(MessageResponse(content="DISPLAY_SEAT_MAP", agent=item.agent.name))
        elif isinstance(item, ToolCallOutputItem):
            events.append(
                AgentEvent(
                    id=uuid4().hex,
                    type="tool_output",
                    agent=item.agent.name,
                    content=str(item.output),
                    metadata={"tool_result": item.output},
                )
            )

    new_context = state["context"].dict()
    changes = {k: new_context[k] for k in new_context if old_context.get(k) != new_context[k]}
    if changes:
        events.append(
            AgentEvent(
                id=uuid4().hex,
                type="context_update",
                agent=current_agent.name,
                content="",
                metadata={"changes": changes},
            )
        )

    state["input_items"] = result.to_input_list()
    state["current_agent"] = current_agent.name
    conversation_store.save(conversation_id, state)

    final_guardrails: List[GuardrailCheck] = []
    for g in getattr(current_agent, "input_guardrails", []):
        name = _get_guardrail_name(g)
        failed = next((gc for gc in final_guardrails if gc.name == name), None)
        if failed:
            final_guardrails.append(failed)
        else:
            final_guardrails.append(
                GuardrailCheck(
                id=uuid4().hex,
                name=name,
                input=req.message,
                reasoning="",
                passed=True,
                timestamp=time.time() * 1000,
                )
            )

    return ChatResponse(
        conversation_id=conversation_id,
        current_agent=current_agent.name,
        messages=messages,
        events=events,
        context=state["context"].dict(),
        agents=registry.list_agents(),
        guardrails=final_guardrails,
    )
