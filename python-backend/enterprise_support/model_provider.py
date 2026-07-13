from __future__ import annotations

import os
from dataclasses import dataclass

from agents import OpenAIChatCompletionsModel, set_tracing_disabled
from openai import AsyncOpenAI

DEFAULT_ZAI_BASE_URL = "https://open.bigmodel.cn/api/paas/v4/"
DEFAULT_ZAI_AGENT_MODEL = "glm-5.2"
DEFAULT_ZAI_GUARDRAIL_MODEL = "glm-5.2"


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


@dataclass(frozen=True)
class ZaiSettings:
    api_key: str | None
    base_url: str
    agent_model: str
    guardrail_model: str

    @classmethod
    def from_env(cls) -> "ZaiSettings":
        return cls(
            api_key=os.getenv("ZAI_API_KEY") or None,
            base_url=os.getenv("ZAI_BASE_URL", DEFAULT_ZAI_BASE_URL),
            agent_model=os.getenv("ZAI_AGENT_MODEL", DEFAULT_ZAI_AGENT_MODEL),
            guardrail_model=os.getenv(
                "ZAI_GUARDRAIL_MODEL", DEFAULT_ZAI_GUARDRAIL_MODEL
            ),
        )

    @property
    def configured(self) -> bool:
        return bool(self.api_key)


ZAI_SETTINGS = ZaiSettings.from_env()

# Non-OpenAI model runs must not attempt to export traces with the provider key.
set_tracing_disabled(_env_flag("OPENAI_TRACING_DISABLED", True))

# Keep application metadata endpoints available before a key is configured. The
# chat endpoint rejects requests before this placeholder can be sent upstream.
ZAI_CLIENT = AsyncOpenAI(
    api_key=ZAI_SETTINGS.api_key or "zai-key-not-configured",
    base_url=ZAI_SETTINGS.base_url,
    max_retries=2,
    timeout=60.0,
)

ZAI_AGENT_MODEL = OpenAIChatCompletionsModel(
    model=ZAI_SETTINGS.agent_model,
    openai_client=ZAI_CLIENT,
)

ZAI_GUARDRAIL_MODEL = OpenAIChatCompletionsModel(
    model=ZAI_SETTINGS.guardrail_model,
    openai_client=ZAI_CLIENT,
)
