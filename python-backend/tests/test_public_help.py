"""Offline acceptance checks; no API keys or external requests are used."""

import asyncio
import json
import os
import subprocess
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from agents import Model, ModelResponse, RunContextWrapper, Usage, set_tracing_disabled
from agents.tool_context import ToolContext
from fastapi.testclient import TestClient
from openai.types.responses import (
    Response,
    ResponseCompletedEvent,
    ResponseFunctionToolCall,
    ResponseOutputItemAddedEvent,
    ResponseOutputItemDoneEvent,
    ResponseOutputMessage,
    ResponseOutputText,
)

from airline.public_help import UNAVAILABLE, public_help_lookup, public_help_server


SOURCE_URL = "https://www.tsa.gov/travel/security-screening/liquids-aerosols-gels-rule"
SEARCH_TERMS = "site:tsa.gov carry on liquids"
SEARCH_RESULT = json.dumps({"results": [{
    "url": SOURCE_URL,
    "title": "Liquids rule",
    "excerpts": ["See the official liquids guidance before packing."],
}]})


def result(text=SEARCH_RESULT, *, error=False):
    # Use MCP's wire representation so this works with either supported Python SDK.
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)] if text else [],
        model_dump=lambda **kwargs: {"isError": error},
    )


def mock_server(response=None):
    server = AsyncMock()
    server.__aenter__.return_value = server
    server.call_tool.return_value = response if response is not None else result()
    return server


def tool_context(context=None):
    return ToolContext.from_agent_context(
        RunContextWrapper(context=context), tool_name="public_help_lookup",
        tool_call_id="test_call", tool_arguments="{}",
    )


class LookupTests(unittest.IsolatedAsyncioTestCase):
    async def test_query_and_original_source_survive(self):
        server = mock_server()
        with patch("airline.public_help.public_help_server", return_value=server):
            output = await public_help_lookup.on_invoke_tool(
                tool_context({"confirmation_number": "PRIVATE-FIXTURE"}),
                json.dumps({"search_terms": SEARCH_TERMS}),
            )
        self.assertIn(SOURCE_URL, output)
        name, arguments = server.call_tool.call_args.args
        self.assertEqual(name, "web_search")
        self.assertEqual(arguments["search_queries"], [SEARCH_TERMS])
        self.assertNotIn("PRIVATE-FIXTURE", json.dumps(arguments))
        self.assertEqual(set(arguments), {"objective", "search_queries"})
        server.__aexit__.assert_awaited_once()

    async def test_tool_errors_and_empty_results_are_not_guidance(self):
        for response in (result(error=True), result(text="")):
            with self.subTest(response=response):
                with patch("airline.public_help.public_help_server", return_value=mock_server(response)):
                    output = await public_help_lookup.on_invoke_tool(
                        tool_context(), json.dumps({"search_terms": SEARCH_TERMS})
                    )
                self.assertEqual(output, UNAVAILABLE)

    async def test_blank_query_does_not_connect(self):
        with patch("airline.public_help.public_help_server") as factory:
            output = await public_help_lookup.on_invoke_tool(
                tool_context(), json.dumps({"search_terms": "  "})
            )
        self.assertEqual(output, UNAVAILABLE)
        factory.assert_not_called()

    async def test_connection_auth_rate_limit_and_timeout_fail_closed(self):
        for error in (ConnectionError("offline"), PermissionError("401"), RuntimeError("429"), TimeoutError()):
            with self.subTest(error=error):
                server = mock_server()
                server.call_tool.side_effect = error
                with patch("airline.public_help.public_help_server", return_value=server):
                    output = await public_help_lookup.on_invoke_tool(
                        tool_context(), json.dumps({"search_terms": SEARCH_TERMS})
                    )
                self.assertEqual(output, UNAVAILABLE)
                server.call_tool.assert_awaited_once()
                server.__aexit__.assert_awaited_once()

    async def test_cancellation_propagates(self):
        server = mock_server()
        server.call_tool.side_effect = asyncio.CancelledError()
        with patch("airline.public_help.public_help_server", return_value=server):
            with self.assertRaises(asyncio.CancelledError):
                await public_help_lookup.on_invoke_tool(
                    tool_context(), json.dumps({"search_terms": SEARCH_TERMS})
                )
        server.__aexit__.assert_awaited_once()

    def test_transport_is_anonymous_and_bounded(self):
        server = public_help_server()
        self.assertEqual(server.params["headers"], {"User-Agent": "openai-cs-agents-demo/public-help"})
        self.assertEqual(server.params["timeout"], 10)
        self.assertEqual(server.params["sse_read_timeout"], 30)
        self.assertEqual(server.client_session_timeout_seconds, 30)


class ScriptedModel(Model):
    """Exercise real orchestration/streaming with deterministic model decisions."""

    async def get_response(self, system_instructions, input, model_settings, tools, output_schema, handoffs, tracing, **kwargs):
        field = "is_relevant" if "is_relevant" in system_instructions else "is_safe"
        return ModelResponse(
            output=[self.message(json.dumps({"reasoning": "Public travel question", field: True}))],
            usage=Usage(), response_id=uuid4().hex,
        )

    @staticmethod
    def message(text):
        return ResponseOutputMessage(
            id="msg_" + uuid4().hex, role="assistant", status="completed", type="message",
            content=[ResponseOutputText(text=text, annotations=[], type="output_text")],
        )

    async def stream_response(self, system_instructions, input, model_settings, tools, output_schema, handoffs, tracing, **kwargs):
        if "You are a helpful triaging agent" in system_instructions:
            assert "public travel guidance" in system_instructions
            name = next(h.tool_name for h in handoffs if h.agent_name == "FAQ Agent")
            output = ResponseFunctionToolCall(
                id=uuid4().hex, call_id=uuid4().hex, name=name, arguments="{}", type="function_call",
            )
        elif not any(item.get("type") == "function_call" and item.get("name") == "public_help_lookup" for item in input):
            assert "original source URL" in system_instructions
            assert "untrusted reference" in system_instructions
            assert "public_help_lookup" in [t.name for t in tools]
            output = ResponseFunctionToolCall(
                id=uuid4().hex, call_id=uuid4().hex, name="public_help_lookup",
                arguments=json.dumps({"search_terms": SEARCH_TERMS}), type="function_call",
            )
        else:
            # Copy a URL actually returned by the tool, rather than a hardcoded final answer.
            tool_output = input[-1]["output"]
            if tool_output == UNAVAILABLE:
                output = self.message("I could not verify the public guidance. Please try again later.")
            else:
                source = json.loads(tool_output)["results"][0]
                output = self.message(f'{source["excerpts"][0]} [Official help]({source["url"]})')
        yield ResponseOutputItemAddedEvent(
            item=output, output_index=0, sequence_number=0, type="response.output_item.added",
        )
        yield ResponseOutputItemDoneEvent(
            item=output, output_index=0, sequence_number=1, type="response.output_item.done",
        )
        yield ResponseCompletedEvent(
            type="response.completed", sequence_number=2,
            response=Response(
                id=uuid4().hex, created_at=0, model="test", object="response", output=[output],
                parallel_tool_calls=False, tool_choice="auto", tools=[], status="completed",
            ),
        )


class ChatTests(unittest.TestCase):
    def test_opt_in_and_default_configuration(self):
        script = """
from airline.agents import faq_agent, triage_agent
import json
print(json.dumps({"tools": [t.name for t in faq_agent.tools],
                  "instructions": faq_agent.instructions,
                  "triage": triage_agent.instructions}))
"""
        for setting in (None, "0", "1"):
            with self.subTest(setting=setting):
                env = os.environ.copy()
                env.pop("ENABLE_PUBLIC_HELP_LOOKUP", None)
                if setting is not None:
                    env["ENABLE_PUBLIC_HELP_LOOKUP"] = setting
                config = json.loads(subprocess.check_output([sys.executable, "-c", script], env=env))
                self.assertEqual("public_help_lookup" in config["tools"], setting == "1")
                self.assertIn("faq_lookup_tool", config["tools"])
                if setting != "1":
                    self.assertNotIn("public_help_lookup", config["instructions"])

    def test_chatkit_handoff_lookup_and_final_source_link(self):
        self.check_chat(result(), SOURCE_URL)

    def test_chatkit_lookup_failure_has_no_fabricated_source(self):
        self.check_chat(result(error=True), "could not verify")

    def check_chat(self, response, expected):
        # Import the application as the documented opt-in startup would.
        with patch.dict(os.environ, {"ENABLE_PUBLIC_HELP_LOOKUP": "1"}):
            import main
            from airline import agents, guardrails
        self.assertIn("public_help_lookup", [t.name for t in agents.faq_agent.tools])
        from server import AirlineServer
        server = AirlineServer()
        model = ScriptedModel()
        set_tracing_disabled(True)
        with (
            patch.object(agents.triage_agent, "model", model),
            patch.object(agents.faq_agent, "model", model),
            patch.object(guardrails.guardrail_agent, "model", model),
            patch.object(guardrails.jailbreak_guardrail_agent, "model", model),
            patch("airline.public_help.public_help_server", return_value=mock_server(response)) as factory,
        ):
            main.app.dependency_overrides[main.get_server] = lambda: server
            try:
                with TestClient(main.app) as client:
                    reply = client.post("/chatkit", json={
                        "type": "threads.create", "metadata": {}, "params": {"input": {
                            "content": [{"type": "input_text", "text":
                                "Find the official TSA help page about carry-on liquids and include the source link."}],
                            "attachments": [], "inference_options": {},
                        }},
                    })
                self.assertEqual(reply.status_code, 200, reply.text)
                events = [json.loads(line[6:]) for line in reply.text.splitlines() if line.startswith("data: ")]
                messages = [e["item"] for e in events if e.get("type") == "thread.item.done"
                            and e.get("item", {}).get("type") == "assistant_message"]
                self.assertTrue(messages, reply.text)
                final = messages[-1]["content"][0]["text"]
                self.assertIn(expected, final)
                if expected == SOURCE_URL:
                    self.assertIn(f"]({SOURCE_URL})", final)
                else:
                    self.assertNotIn("https://", final)
                state = next(iter(server._state.values()))
                self.assertEqual(state.current_agent_name, "FAQ Agent")
                self.assertTrue(all(check.passed for check in state.guardrails))
                self.assertEqual(state.context.model_dump(), main.create_initial_context().model_dump())
                factory.assert_called_once()
            finally:
                main.app.dependency_overrides.clear()


if __name__ == "__main__":
    unittest.main()
