from agents import OpenAIChatCompletionsModel

from enterprise_support.agents import ALL_AGENTS
from enterprise_support.model_provider import (
    DEFAULT_ZAI_AGENT_MODEL,
    DEFAULT_ZAI_BASE_URL,
    DEFAULT_ZAI_GUARDRAIL_MODEL,
    ZaiSettings,
)


def test_zai_settings_use_safe_defaults(monkeypatch) -> None:
    for name in (
        "ZAI_API_KEY",
        "ZAI_BASE_URL",
        "ZAI_AGENT_MODEL",
        "ZAI_GUARDRAIL_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = ZaiSettings.from_env()

    assert settings.api_key is None
    assert settings.base_url == DEFAULT_ZAI_BASE_URL
    assert settings.agent_model == DEFAULT_ZAI_AGENT_MODEL
    assert settings.guardrail_model == DEFAULT_ZAI_GUARDRAIL_MODEL
    assert settings.configured is False


def test_all_business_agents_use_zai_chat_completions() -> None:
    for agent in ALL_AGENTS:
        assert isinstance(agent.model, OpenAIChatCompletionsModel)
        assert agent.model.model == DEFAULT_ZAI_AGENT_MODEL
        assert agent.model_settings.extra_body == {
            "thinking": {"type": "disabled"}
        }
