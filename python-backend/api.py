from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from uuid import uuid4
import time
import logging

from main import (
    triage_agent,
    faq_agent,
    seat_booking_agent,
    flight_status_agent,
    cancellation_agent,
    create_initial_context,
)

from agents import (
    Runner,
    ItemHelpers,
    MessageOutputItem,
    HandoffOutputItem,
    ToolCallItem,
    ToolCallOutputItem,
    InputGuardrailTripwireTriggered,
    Handoff,
    ModelConfig, # Required if we were to use it directly
)
import os # For GOOGLE_API_KEY
import google.generativeai as genai # For Gemini client
from dotenv import load_dotenv # To load .env

load_dotenv() # Load environment variables from .env file

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Determine model provider and configure Gemini if selected
MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "openai")
if MODEL_PROVIDER == "gemini":
    GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")
    if not GEMINI_API_KEY:
        logger.error("MODEL_PROVIDER is 'gemini' but GOOGLE_API_KEY is not set.")
        # Potentially raise an error or switch to a default
    else:
        try:
            genai.configure(api_key=GEMINI_API_KEY)
            logger.info("Gemini API configured successfully.")
        except Exception as e:
            logger.error(f"Error configuring Gemini API: {e}")

# This is a placeholder for where the actual Gemini client call would happen
# if the openai-agents SDK's Runner doesn't support it directly.
# We'll need to modify how Runner.run works or bypass it for Gemini.

async def run_gemini_agent(agent, input_items, context):
    # This is a simplified example and needs to be fully implemented
    # to match the capabilities of the openai-agents Runner, including
    # tool use, handoffs, context management, etc.

    # Assuming agent.model is the Gemini model name string
    model_name = agent.model
    if not isinstance(model_name, str) or not model_name.startswith("gemini-"):
        # Fallback or error if it's not a Gemini model string as expected
        # This indicates that get_model_config in main.py didn't return a gemini model name
        # or this function was called with an OpenAI model.
        logger.warning(f"run_gemini_agent called with non-Gemini model: {model_name}. Falling back to OpenAI Runner.")
        # This fallback is a simplification. In reality, you'd ensure this function is only called for Gemini.
        return await Runner.run(agent, input_items, context=context)

    gemini_model = genai.GenerativeModel(model_name)

    # Construct prompt for Gemini from input_items and agent.instructions
    # The `input_items` is a list of dictionaries like:
    # [{'content': 'Can I change my seat?', 'role': 'user'}]
    # The `agent.instructions` can be a string or a callable.

    # Convert openai-style messages to Gemini's format if necessary
    # Gemini expects a list of `glm.Content` objects or simple strings.
    # For chat, it's usually: [{'role': 'user', 'parts': [{'text': '...'}]}, {'role': 'model', 'parts': [{'text': '...'}]}]

    current_prompt = []
    for item in input_items:
        role = "user" if item.get("role") == "user" else "model"
        current_prompt.append({"role": role, "parts": [{"text": item.get("content")}]})

    # Add system instructions. Gemini handles this differently.
    # Sometimes it's part of the first user message, or via system_instruction parameter.
    # For simplicity, let's prepend it to the prompt.
    instructions_text = ""
    if callable(agent.instructions):
        # Assuming RunContextWrapper can be created or mocked if necessary
        # This part is complex because agent.instructions might expect a RunContextWrapper
        # For now, let's assume it can be called simply or we simplify this.
        # This is a placeholder:
        # from main import AirlineAgentContext # This creates a circular dependency, resolve later
        # fake_run_context = RunContextWrapper(context=context, agent=agent)
        # instructions_text = agent.instructions(fake_run_context, agent)
        pass # Requires more robust handling of RunContextWrapper
    elif isinstance(agent.instructions, str):
        instructions_text = agent.instructions

    # Prepending instructions to the first user message or as a system message if API supports
    # For now, just add it to the history as a model preamble if not empty
    # This is a simplification. Proper instruction handling for Gemini is important.
    if instructions_text:
         # Gemini API prefers system instructions via `system_instruction` parameter of `GenerativeModel`
         # or as the first part of the `contents` list with role 'system' (though 'system' role is more for older APIs or specific configurations)
         # For `genai.GenerativeModel(model_name, system_instruction=instructions_text)`
         # Let's try to re-initialize the model with system instructions
        try:
            gemini_model = genai.GenerativeModel(model_name, system_instruction=instructions_text)
            logger.info(f"Gemini model re-initialized with system instructions for {agent.name}")
        except Exception as e:
            logger.error(f"Could not set system_instruction for Gemini model: {e}. Instructions will be part of the prompt.")
            # Fallback: Prepend to prompt if system_instruction is not available/fails for the model
            current_prompt.insert(0, {"role": "model", "parts": [{"text": f"System Instructions: {instructions_text}"}]})


    logger.info(f"Running Gemini agent {agent.name} with model {model_name}")
    logger.info(f"Gemini prompt: {current_prompt}")

    # Handle tools (function calling)
    gemini_tools = None
    if agent.tools:
        # Convert OpenAI tools to Gemini format
        # This is a major task and depends on the structure of `agent.tools`
        # and how `openai-agents` defines them.
        # For now, this is a placeholder.
        # See: https://ai.google.dev/gemini-api/docs/function-calling
        logger.warning("Gemini tool conversion is not fully implemented yet.")
        # gemini_tools = [...]
        pass

    try:
        if gemini_tools:
            response = await gemini_model.generate_content_async(current_prompt, tools=gemini_tools)
        else:
            response = await gemini_model.generate_content_async(current_prompt)

        # Process response
        # This needs to create a result structure compatible with what the rest of api.py expects
        # (e.g., `Runner.Result` with `new_items`, `final_output_as`, etc.)

        # Example: simple text response
        response_text = response.text
        logger.info(f"Gemini response: {response_text}")

        # This is a mock result. Needs to be structured like Runner.Result
        class MockToolCall:
            def __init__(self, name, arguments):
                self.name = name
                self.arguments = arguments

        class MockMessageOutputItem:
            def __init__(self, agent, content):
                self.agent = agent
                self.content = content # this should be the raw message item
                self.text = content # for ItemHelpers.text_message_output

        class MockRunnerResult:
            def __init__(self, new_items, agent_context):
                self.new_items = new_items
                self._agent_context = agent_context
                self._raw_output = new_items[-1].content if new_items else "" # Simplification

            def to_input_list(self):
                # Convert new_items back to the format expected for state["input_items"]
                return [{"role": "user" if item.agent == "user" else "assistant", "content": item.text} for item in self.new_items] # Simplified

            def final_output_as(self, output_type):
                # This is for guardrails primarily. Needs proper implementation.
                if self._raw_output and hasattr(output_type, "model_validate_json"):
                    try:
                        return output_type.model_validate_json(self._raw_output)
                    except Exception as e:
                        logger.error(f"Error validating Gemini output for type {output_type}: {e}")
                        return None
                return None


        # Check for function calls in response.candidates[0].content.parts if type is FUNCTION_CALL
        # For now, assume text response
        processed_new_items = input_items + [{"role": "assistant", "content": response_text}] # Update history

        # We need to adapt the response to create MessageOutputItem, ToolCallItem etc.
        # This is a highly simplified version.
        # If it was a tool call, one item would be ToolCallItem, then ToolCallOutputItem.
        # If it's a message, it's MessageOutputItem.

        # This part needs to mirror the complex logic in openai-agents Runner
        # For now, just return a simple message output
        output_item = MockMessageOutputItem(agent=agent, content=response_text)

        # The Runner.Result also includes the updated context.
        # For now, assume context doesn't change in this simplified Gemini run.
        return MockRunnerResult(new_items=[output_item], agent_context=context)

    except Exception as e:
        logger.error(f"Error calling Gemini API: {e}")
        # Return an error message or raise exception
        # This also needs to be compatible with how errors are handled by the caller
        # For now, make a mock error result
        error_message = f"Sorry, there was an error with the Gemini agent: {e}"
        error_item = MockMessageOutputItem(agent=agent, content=error_message)
        return MockRunnerResult(new_items=[error_item], agent_context=context)


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# CORS configuration (adjust as needed for deployment)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# Models
# =========================

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

# =========================
# In-memory store for conversation state
# =========================

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

# TODO: when deploying this app in scale, switch to your own production-ready implementation
conversation_store = InMemoryConversationStore()

# =========================
# Helpers
# =========================

def _get_agent_by_name(name: str):
    """Return the agent object by name."""
    agents = {
        triage_agent.name: triage_agent,
        faq_agent.name: faq_agent,
        seat_booking_agent.name: seat_booking_agent,
        flight_status_agent.name: flight_status_agent,
        cancellation_agent.name: cancellation_agent,
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
        make_agent_dict(seat_booking_agent),
        make_agent_dict(flight_status_agent),
        make_agent_dict(cancellation_agent),
    ]

# =========================
# Main Chat Endpoint
# =========================

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    """
    Main chat endpoint for agent orchestration.
    Handles conversation state, agent routing, and guardrail checks.
    """
    # Initialize or retrieve conversation state
    is_new = not req.conversation_id or conversation_store.get(req.conversation_id) is None
    if is_new:
        conversation_id: str = uuid4().hex
        ctx = create_initial_context()
        current_agent_name = triage_agent.name
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
                agents=_build_agents_list(),
                guardrails=[],
            )
    else:
        conversation_id = req.conversation_id  # type: ignore
        state = conversation_store.get(conversation_id)

    current_agent = _get_agent_by_name(state["current_agent"])
    state["input_items"].append({"content": req.message, "role": "user"})
    old_context = state["context"].model_dump().copy()
    guardrail_checks: List[GuardrailCheck] = [] # Store results of all guardrail checks

    try:
        # Determine if the current agent is intended to use Gemini
        is_gemini_model_for_current_agent = MODEL_PROVIDER == "gemini" and \
                                           isinstance(current_agent.model, str) and \
                                           current_agent.model.startswith("gemini-")

        # --- Input Guardrail Execution ---
        if hasattr(current_agent, "input_guardrails") and current_agent.input_guardrails:
            for guardrail_fn_decorator in current_agent.input_guardrails:
                # `guardrail_fn_decorator` is the callable like `main.relevance_guardrail`.
                # This function, when called, will internally use `Runner.run` on its own specific
                # guardrail agent (e.g., `main.guardrail_agent`).
                # The `main.guardrail_agent.model` will be a Gemini model string if MODEL_PROVIDER="gemini"
                # due to `get_model_config()` in main.py.
                #
                # CRITICAL POINT: The `agents.Runner.run` from the `openai-agents` SDK is most likely
                # hardcoded to call OpenAI. If `main.guardrail_agent.model` is "gemini-...",
                # the SDK's `Runner.run` will likely fail or misinterpret the model.
                # A full Gemini integration for guardrails would require:
                #    a) Modifying the `openai-agents` SDK's Runner to be model-agnostic.
                #    b) Replacing the SDK's guardrail mechanism with a custom one that can use `run_gemini_agent`.
                # For this iteration, we acknowledge this limitation: True Gemini-backed guardrails may not function
                # correctly and might either error out or silently fail if the SDK's Runner can't handle them.
                # The `InputGuardrailTripwireTriggered` exception path relies on the SDK's behavior.

                logger.info(f"Evaluating input guardrail: {_get_guardrail_name(guardrail_fn_decorator)} for agent {current_agent.name}")

                from agents import RunContextWrapper # Make sure it's available

                guardrail_input_message = req.message
                passed_check = True
                reasoning_text = ""
                output_info_for_guardrail = None

                try:
                    # Call the decorated guardrail function (e.g., `relevance_guardrail`)
                    # It expects (RunContextWrapper, current_agent, message_string)
                    guardrail_run_result = await guardrail_fn_decorator(
                        RunContextWrapper(context=state["context"], agent=current_agent),
                        current_agent, # The agent whose input is being guarded
                        guardrail_input_message
                    )
                    # `guardrail_run_result` is a `GuardrailFunctionOutput`
                    output_info_for_guardrail = guardrail_run_result.output_info
                    reasoning_text = getattr(output_info_for_guardrail, "reasoning", "")

                    if guardrail_run_result.tripwire_triggered:
                        passed_check = False
                        logger.warning(f"Input guardrail {_get_guardrail_name(guardrail_fn_decorator)} FAILED for agent {current_agent.name}. Reasoning: {reasoning_text}")

                        # Add this failed check to guardrail_checks for UI
                        guardrail_checks.append(GuardrailCheck(
                            id=uuid4().hex,
                            name=_get_guardrail_name(guardrail_fn_decorator),
                            input=guardrail_input_message,
                            reasoning=reasoning_text,
                            passed=False,
                            timestamp=time.time() * 1000,
                        ))

                        # Populate other guardrails as passed (as per original logic)
                        for other_g_fn in current_agent.input_guardrails:
                            if other_g_fn != guardrail_fn_decorator:
                                guardrail_checks.append(GuardrailCheck(
                                    id=uuid4().hex,
                                    name=_get_guardrail_name(other_g_fn),
                                    input=guardrail_input_message,
                                    reasoning="", # No reasoning as it passed or wasn't this one
                                    passed=True,
                                    timestamp=time.time() * 1000,
                                ))

                        refusal_msg = "Sorry, I can only answer questions related to airline travel."
                        state["input_items"].append({"role": "assistant", "content": refusal_msg})
                        conversation_store.save(conversation_id, state)
                        return ChatResponse(
                            conversation_id=conversation_id,
                            current_agent=current_agent.name,
                            messages=[MessageResponse(content=refusal_msg, agent=current_agent.name)],
                            events=[],
                            context=state["context"].model_dump(),
                            agents=_build_agents_list(),
                            guardrails=guardrail_checks, # Send all checks made so far
                        )
                    else: # Guardrail passed
                        logger.info(f"Input guardrail {_get_guardrail_name(guardrail_fn_decorator)} PASSED for agent {current_agent.name}. Reasoning: {reasoning_text}")
                        guardrail_checks.append(GuardrailCheck(
                            id=uuid4().hex,
                            name=_get_guardrail_name(guardrail_fn_decorator),
                            input=guardrail_input_message,
                            reasoning=reasoning_text, # Show reasoning even for passed checks
                            passed=True,
                            timestamp=time.time() * 1000,
                        ))

                except InputGuardrailTripwireTriggered as e_sdk:
                    # This handles the case where the SDK's Runner (used internally by the guardrail_fn_decorator)
                    # itself raises the exception, e.g. if it was an OpenAI guardrail agent that tripped.
                    passed_check = False
                    failed_guardrail_sdk = e_sdk.guardrail_result.guardrail # This is the guardrail_fn_decorator
                    output_info_for_guardrail = e_sdk.guardrail_result.output.output_info
                    reasoning_text = getattr(output_info_for_guardrail, "reasoning", "")
                    logger.warning(f"Input guardrail {_get_guardrail_name(failed_guardrail_sdk)} FAILED (via SDK exception) for agent {current_agent.name}. Reasoning: {reasoning_text}")

                    # Add this failed check
                    guardrail_checks.append(GuardrailCheck(
                        id=uuid4().hex,
                        name=_get_guardrail_name(failed_guardrail_sdk),
                        input=guardrail_input_message,
                        reasoning=reasoning_text,
                        passed=False,
                        timestamp=time.time() * 1000,
                    ))
                    # Populate others as passed
                    for other_g_fn_sdk in current_agent.input_guardrails:
                        if other_g_fn_sdk != failed_guardrail_sdk:
                            guardrail_checks.append(GuardrailCheck(
                                id=uuid4().hex,
                                name=_get_guardrail_name(other_g_fn_sdk),
                                input=guardrail_input_message,
                                reasoning="",
                                passed=True,
                                timestamp=time.time() * 1000,
                            ))

                    refusal_msg_sdk = "Sorry, I can only answer questions related to airline travel."
                    state["input_items"].append({"role": "assistant", "content": refusal_msg_sdk})
                    conversation_store.save(conversation_id, state)
                    return ChatResponse(
                        conversation_id=conversation_id,
                        current_agent=current_agent.name,
                        messages=[MessageResponse(content=refusal_msg_sdk, agent=current_agent.name)],
                        events=[],
                        context=state["context"].model_dump(),
                        agents=_build_agents_list(),
                        guardrails=guardrail_checks,
                    )
                except Exception as guard_exec_err:
                    logger.error(f"Error during execution of guardrail {_get_guardrail_name(guardrail_fn_decorator)}: {guard_exec_err}. Failing open for this guardrail.")
                    # Log as "passed" but with an error note in reasoning, or handle as a system error
                    guardrail_checks.append(GuardrailCheck(
                        id=uuid4().hex,
                        name=_get_guardrail_name(guardrail_fn_decorator),
                        input=guardrail_input_message,
                        reasoning=f"Error during guardrail execution: {guard_exec_err}",
                        passed=True, # Failing open
                        timestamp=time.time() * 1000,
                    ))


        # --- Main Agent Logic Execution ---
        # If all input guardrails passed (or none were configured to stop execution):
        if is_gemini_model_for_current_agent:
            logger.info(f"Running GEMINI agent: {current_agent.name} with model {current_agent.model}")
            result = await run_gemini_agent(current_agent, state["input_items"], context=state["context"])
        else:
            logger.info(f"Running OPENAI agent: {current_agent.name} with model {current_agent.model}")
            # This path will use the original openai-agents SDK Runner.run, which includes its own
            # input guardrail processing. If guardrails were already handled above, they might run again
            # if not structured carefully. The SDK's Runner.run raises InputGuardrailTripwireTriggered.
            # However, our manual guardrail loop above should catch trips and return BEFORE this.
            # So, if we reach here, it means either:
            #   1. MODEL_PROVIDER is "openai".
            #   2. MODEL_PROVIDER is "gemini" BUT the current_agent.model is NOT a gemini model string (config error).
            #   3. Our manual guardrail handling for Gemini path had an issue and didn't return.
            # The `InputGuardrailTripwireTriggered` exception below is thus mainly for the OpenAI path.
            result = await Runner.run(current_agent, state["input_items"], context=state["context"])

    except InputGuardrailTripwireTriggered as e:
        # This block is now mostly for the OpenAI path, if its Runner.run triggers a guardrail.
        # Or if our Gemini guardrail handling somehow re-raises or lets this specific exception through.
        logger.warning(f"InputGuardrailTripwireTriggered caught by SDK's Runner for agent {current_agent.name}")
        failed_guard = e.guardrail_result.guardrail # This is the guardrail function (e.g. main.relevance_guardrail)
        gr_output = e.guardrail_result.output.output_info
        gr_reasoning = getattr(gr_output, "reasoning", "")
        gr_input = req.message # User's message that triggered the guardrail
        gr_timestamp = time.time() * 1000

        # Ensure guardrail_checks list is populated correctly for the UI
        # The `failed_guard` is the specific guardrail function that was tripped.
        # Other guardrails associated with the agent should be marked as passed if not already processed.
        processed_guardrail_names = {gc.name for gc in guardrail_checks}

        if _get_guardrail_name(failed_guard) not in processed_guardrail_names:
            guardrail_checks.append(GuardrailCheck(
                id=uuid4().hex,
                name=_get_guardrail_name(failed_guard),
                input=gr_input,
                reasoning=gr_reasoning, # Reasoning for the failed one
                passed=False,
                timestamp=gr_timestamp,
            ))
            processed_guardrail_names.add(_get_guardrail_name(failed_guard))

        for g_fn_sdk in current_agent.input_guardrails:
            g_name = _get_guardrail_name(g_fn_sdk)
            if g_name not in processed_guardrail_names:
                guardrail_checks.append(GuardrailCheck(
                    id=uuid4().hex,
                    name=g_name,
                    input=gr_input,
                    reasoning="", # No reasoning as it passed or wasn't evaluated to fail here
                    passed=True,
                    timestamp=gr_timestamp,
                ))

        refusal = "Sorry, I can only answer questions related to airline travel." # Standard refusal message
        state["input_items"].append({"role": "assistant", "content": refusal})
        # Save state before returning
        conversation_store.save(conversation_id, state)
        return ChatResponse(
            conversation_id=conversation_id,
            current_agent=current_agent.name,
            messages=[MessageResponse(content=refusal, agent=current_agent.name)],
            events=[],
            context=state["context"].model_dump(),
            agents=_build_agents_list(),
            guardrails=guardrail_checks,
        )

    messages: List[MessageResponse] = []
    events: List[AgentEvent] = []

    for item in result.new_items:
        if isinstance(item, MessageOutputItem):
            text = ItemHelpers.text_message_output(item)
            messages.append(MessageResponse(content=text, agent=item.agent.name))
            events.append(AgentEvent(id=uuid4().hex, type="message", agent=item.agent.name, content=text))
        # Handle handoff output and agent switching
        elif isinstance(item, HandoffOutputItem):
            # Record the handoff event
            events.append(
                AgentEvent(
                    id=uuid4().hex,
                    type="handoff",
                    agent=item.source_agent.name,
                    content=f"{item.source_agent.name} -> {item.target_agent.name}",
                    metadata={"source_agent": item.source_agent.name, "target_agent": item.target_agent.name},
                )
            )
            # If there is an on_handoff callback defined for this handoff, show it as a tool call
            from_agent = item.source_agent
            to_agent = item.target_agent
            # Find the Handoff object on the source agent matching the target
            ho = next(
                (h for h in getattr(from_agent, "handoffs", [])
                 if isinstance(h, Handoff) and getattr(h, "agent_name", None) == to_agent.name),
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
                    import json
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
            # If the tool is display_seat_map, send a special message so the UI can render the seat selector.
            if tool_name == "display_seat_map":
                messages.append(
                    MessageResponse(
                        content="DISPLAY_SEAT_MAP",
                        agent=item.agent.name,
                    )
                )
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

    # The `guardrail_checks` list should now be populated by the guardrail execution logic above.
    # If no guardrails were tripped and led to an early return, this list will contain
    # records of all guardrails that were checked and passed.
    # If execution was stopped by a guardrail, `guardrail_checks` was populated and returned with the ChatResponse.
    # So, `final_guardrails` can just be `guardrail_checks` if it reached here.
    # If no guardrails were defined on the agent, `guardrail_checks` will be empty.
    # We still need to ensure that if there were guardrails defined, but none of them were
    # added to `guardrail_checks` (e.g. due to an error before the check or if they all passed silently
    # without being added to the list), they are shown as passed.

    final_guardrails_ui: List[GuardrailCheck] = list(guardrail_checks) # Start with what we've collected

    # Ensure all defined input guardrails for the current agent have an entry in final_guardrails_ui
    # (either from a failed check, a passed check, or mark as passed by default if not already listed)
    defined_guardrail_names_on_agent = {_get_guardrail_name(g) for g in getattr(current_agent, "input_guardrails", [])}
    ui_reported_guardrail_names = {gc.name for gc in final_guardrails_ui}

    for name in defined_guardrail_names_on_agent:
        if name not in ui_reported_guardrail_names:
            # This guardrail was defined but not explicitly recorded as failed or passed during the run.
            # This can happen if the main agent logic was reached without any guardrail interaction
            # that explicitly added to `guardrail_checks`. Assume it passed.
            final_guardrails_ui.append(GuardrailCheck(
                id=uuid4().hex,
                name=name,
                input=req.message, # The user input for this turn
                reasoning="Assumed passed (not explicitly evaluated or no tripwire).",
                passed=True,
                timestamp=time.time() * 1000,
            ))

    return ChatResponse(
        conversation_id=conversation_id,
        current_agent=current_agent.name,
        messages=messages,
        events=events,
        context=state["context"].dict(),
        agents=_build_agents_list(),
        guardrails=final_guardrails_ui, # Use the consolidated list
    )
