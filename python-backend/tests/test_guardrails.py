import json

import httpx
import pytest
from agents import Agent, OpenAIChatCompletionsModel, Runner
from openai import AsyncOpenAI

from enterprise_support.guardrails import (
    GUARDRAIL_MODEL_SETTINGS,
    _relevance_output_or_block,
    _safety_output_or_block,
)


def test_relevance_output_parses_json() -> None:
    result = _relevance_output_or_block(
        '{"reasoning":"AI support question","is_relevant":true}'
    )

    assert result.is_relevant is True
    assert result.reasoning == "AI support question"


def test_safety_output_accepts_fenced_json() -> None:
    result = _safety_output_or_block(
        '```json\n{"reasoning":"normal request","is_safe":true}\n```'
    )

    assert result.is_safe is True


def test_guardrails_fail_closed_on_invalid_output() -> None:
    relevance = _relevance_output_or_block("not-json")
    safety = _safety_output_or_block("not-json")

    assert relevance.is_relevant is False
    assert safety.is_safe is False
    assert "validation failed" in relevance.reasoning
    assert "validation failed" in safety.reasoning


@pytest.mark.asyncio
async def test_guardrail_model_sends_zai_compatible_json_mode() -> None:
    captured: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "created": 1,
                "model": "glm-test",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": '{"reasoning":"safe","is_safe":true}',
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                },
            },
        )

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = AsyncOpenAI(
        api_key="test-key",
        base_url="https://example.test/v4/",
        http_client=http_client,
    )
    model = OpenAIChatCompletionsModel(model="glm-test", openai_client=client)
    agent = Agent(
        name="Guardrail request test",
        instructions="Return a JSON safety decision.",
        model=model,
        model_settings=GUARDRAIL_MODEL_SETTINGS,
    )

    try:
        result = await Runner.run(agent, "hello")
    finally:
        await client.close()

    assert result.final_output == '{"reasoning":"safe","is_safe":true}'
    assert captured["model"] == "glm-test"
    assert captured["response_format"] == {"type": "json_object"}
    assert captured["thinking"] == {"type": "disabled"}
