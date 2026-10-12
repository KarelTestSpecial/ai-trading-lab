"""Google AI Studio (Gemini) client over the REST API.

Kept to the standard library (no SDK) so the AI layer stays dependency-light and
auditable. Free-tier only (PLAN.md §9); a missing key is a hard error rather than
a silent fallback, so the pipeline never pretends a judgment came from an LLM
when it did not.

Docs: https://ai.google.dev/api/generate-content
"""

from __future__ import annotations

from cadence_core.judgment.base import JudgmentError

from src.data.http import http_post_json

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def extract_text(payload: dict) -> str:
    """Pull the first text part out of a Gemini generateContent response."""
    try:
        candidates = payload["candidates"]
        parts = candidates[0]["content"]["parts"]
        return "".join(part.get("text", "") for part in parts)
    except (KeyError, IndexError, TypeError) as exc:
        raise JudgmentError(f"unexpected Gemini response: {payload!r}") from exc


class GeminiClient:
    def __init__(self, api_key: str | None, *, model: str = "gemini-2.0-flash", timeout: float = 30.0):
        if not api_key:
            raise JudgmentError("GeminiClient requires a GOOGLE_API_KEY")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def complete(self, prompt: str, *, system: str | None = None) -> str:
        payload: dict = {"contents": [{"parts": [{"text": prompt}]}]}
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        url = GEMINI_URL.format(model=self.model)
        data = http_post_json(url, payload, headers={"x-goog-api-key": self.api_key}, timeout=self.timeout)
        return extract_text(data)
