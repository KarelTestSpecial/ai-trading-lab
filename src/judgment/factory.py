"""Build a judgment model from a name and settings (shared by CLI and loop)."""

from __future__ import annotations

from cadence_core.judgment.base import JudgmentError, JudgmentModel
from cadence_core.judgment.jev import JevAdapter, JevClient

from src.config import Settings
from src.judgment.gemini import GeminiClient
from src.judgment.rules import RuleBasedJudge

__all__ = ["build_judge"]


def build_judge(name: str, settings: Settings) -> JudgmentModel:
    key = name.strip().lower()
    if key == "rules":
        return RuleBasedJudge()
    if key == "gemini":
        return GeminiClient(settings.google_api_key)
    if key == "jev":
        return JevAdapter(JevClient(settings))
    raise JudgmentError(f"unknown judge {name!r}; choose rules, gemini or jev")
