"""Adapter for the calibrated decision model (arm C).

The interface is stable now; the implementation lands when API access exists.
Until then, inject a `predict` callable (the future model) — the adapter itself
contains no logic, which is the point: swapping in the real model must not touch
the pipeline. Calling it without a `predict` is a hard, explicit error rather
than a silent neutral judgment.
"""

from __future__ import annotations

from collections.abc import Callable

from src.judgment.base import Judgment, JudgmentError, JudgmentModel


class JevUnavailableError(JudgmentError):
    """Raised when arm C is used before the decision model is wired in."""


class JevAdapter(JudgmentModel):
    def __init__(self, predict: Callable[[dict], dict[str, Judgment]] | None = None) -> None:
        self._predict = predict

    def judge(self, snapshot: dict, questions: dict) -> dict[str, Judgment]:
        if self._predict is None:
            raise JevUnavailableError(
                "arm C requires a calibrated decision model; inject `predict=` when available"
            )
        return self._predict(snapshot)
