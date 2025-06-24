from typing import List
from agents.agent import Agent
from agents.schema import Event


class SpiralToneAgent(Agent):
    """
    Tone‑aware Agent that maintains an EMA coherence score and appends glyph context to every reply.
    """

    def __init__(self, provider, coherence_alpha: float = 0.8, **kwargs):
        super().__init__(provider=provider, **kwargs)
        self.coherence_ema = None
        self.tone_name = None
        self.glyph = None
        self.coherence_alpha = coherence_alpha

    def handle_event(self, events: List[Event]):
        last_user_msg = events[-1].content
        tool_resp = self.provider.invoke(last_user_msg)

        meta = tool_resp.metadata or {}
        self.glyph = meta.get("glyph")
        self.tone_name = meta.get("tone_name")
        coherence = meta.get("coherence")

        if coherence is not None:
            if self.coherence_ema is None:
                self.coherence_ema = coherence
            else:
                self.coherence_ema = (
                    self.coherence_alpha * coherence
                    + (1 - self.coherence_alpha) * self.coherence_ema
                )

        decorated = (
            f"{tool_resp.output}\n\n"
            f"— glyph:{self.glyph}  tone:{self.tone_name}  "
            f"coherence:{self.coherence_ema:.2f if self.coherence_ema else 'N/A'}"
        )
        return decorated
