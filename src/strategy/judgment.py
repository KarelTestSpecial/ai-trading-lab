"""Judgment-driven strategy (arms B and C).

Implements the engine's `Strategy` contract by running the full pipeline per
decision: deterministic snapshot -> optional context digest -> judgment model ->
policy. The same class serves every AI arm; only the injected `judge` differs
(LLMJudge for B, JevAdapter for C), which is what makes the arms comparable.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date

from src.context.base import ContextProvider
from src.context.digest import build_digest
from src.data.base import Bar
from src.features.snapshot import FeatureParams, build_snapshot
from src.judgment.base import Judgment, JudgmentModel
from src.judgment.llm import DEFAULT_QUESTIONS
from src.policy.policy import judgment_weights
from src.policy.risk import RiskLimits


class JudgmentStrategy:
    def __init__(
        self,
        judge: JudgmentModel,
        limits: RiskLimits,
        *,
        params: FeatureParams | None = None,
        context_provider: ContextProvider | None = None,
        questions: dict | None = None,
        min_confidence: float = 0.0,
    ) -> None:
        self.judge = judge
        self.limits = limits
        self.params = params or FeatureParams()
        self.context_provider = context_provider
        self.questions = questions or DEFAULT_QUESTIONS
        self.min_confidence = min_confidence
        # Populated on each call so callers (and the journal) can inspect the
        # exact snapshot and judgment behind a decision.
        self.last_snapshots: dict[str, dict] = {}
        self.last_judgments: dict[str, dict[str, Judgment]] = {}

    def _context(self, day: date, symbols: list[str]) -> str | None:
        if self.context_provider is None:
            return None
        return build_digest(self.context_provider.items(symbols, day, day)) or None

    def target_weights(
        self, day: date, history: Mapping[str, Sequence[Bar]]
    ) -> dict[str, float]:
        snapshots = {
            symbol: build_snapshot(symbol, history[symbol], self.params)
            for symbol in sorted(history)
            if history[symbol]
        }
        context = self._context(day, list(snapshots))

        judgments: dict[str, dict[str, Judgment]] = {}
        enriched: dict[str, dict] = {}
        for symbol, snapshot in snapshots.items():
            if context:
                snapshot = {**snapshot, "context": context}
            enriched[symbol] = snapshot
            judgments[symbol] = self.judge.judge(snapshot, self.questions)

        self.last_snapshots = enriched
        self.last_judgments = judgments
        return judgment_weights(judgments, self.limits, min_confidence=self.min_confidence)
