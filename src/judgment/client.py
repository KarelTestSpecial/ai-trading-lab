"""LLM client protocol and offline clients.

The judgment layer never talks to a vendor directly; it talks to an `LLMClient`.
That keeps the vendor (Gemini today, anything tomorrow) swappable and lets tests
run fully offline with a `StaticLLMClient`.
"""

from __future__ import annotations

from typing import Protocol


class LLMClient(Protocol):
    def complete(self, prompt: str, *, system: str | None = None) -> str:
        """Return the model's text completion for `prompt`."""


class StaticLLMClient:
    """Returns a canned response; records the prompts it received (test double)."""

    def __init__(self, response: str) -> None:
        self.response = response
        self.prompts: list[str] = []

    def complete(self, prompt: str, *, system: str | None = None) -> str:
        self.prompts.append(prompt)
        return self.response
