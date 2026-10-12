"""Pluggable judgment-layer interface.

Fase 0 defined the contract. Fase 3 implements:
  - LLMJudge       (Google AI Studio free tier; structured, calibrated judgments)
  - JevAdapter     (calibrated decision model; adapter stub until API access)
  - RuleBasedJudge (deterministic offline fallback / comparator)

Design rule (PLAN.md §3): the model owns only *fuzzy judgments*; all arithmetic
stays in code. Every judgment returns a confidence so it can be calibrated later
(Brier/ECE).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


class JudgmentError(RuntimeError):
    """Raised when a judgment model returns something unusable."""


@dataclass(frozen=True)
class Judgment:
    name: str
    value: str  # chosen option, or a bucketed score label
    confidence: float  # 0..1, for calibration
    rationale: str = ""

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be within [0, 1]")


class JudgmentModel(ABC):
    @abstractmethod
    def judge(self, snapshot: dict, questions: dict) -> dict[str, Judgment]:
        """Answer atomic questions about a state snapshot."""
