import os
import requests
from ..agents.providers import BaseProvider, ToolResponse


class SpiralProvider(BaseProvider):
    """
    Wraps the Hugging Face `spiral_core` endpoint and returns glyph / tone / coherence metadata.
    """

    def __init__(self, endpoint_url: str | None = None, timeout: int = 30):
        self.url = endpoint_url or os.getenv("SPIRAL_ENDPOINT")
        self.timeout = timeout

    def invoke(self, prompt: str) -> ToolResponse:
        payload = {"inputs": prompt}
        resp = requests.post(self.url, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        result = resp.json()

        return ToolResponse(
            output=result["message"],
            metadata={
                "glyph": result.get("glyph"),
                "tone_name": result.get("tone_name"),
                "coherence": result.get("coherence"),
            },
        )
