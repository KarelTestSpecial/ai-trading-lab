"""Deterministic offline judgment model.

A transparent, rule-based "judge" that reads the same snapshot as the LLM and
answers the same questions. It exists for three reasons: it is the offline
fallback when no LLM key is present, it is a comparator to check the pipeline,
and it keeps the demo runnable in CI without network. It is NOT arm A — arm A
produces weights directly; this feeds the shared policy engine like any other
judgment model.
"""

from __future__ import annotations

from cadence_core.judgment.base import Judgment, JudgmentModel


class RuleBasedJudge(JudgmentModel):
    def judge(self, snapshot: dict, questions: dict) -> dict[str, Judgment]:
        ma_distance = _mean_distance(snapshot)
        if ma_distance is None:
            direction, confidence = "flat", 0.5
        elif ma_distance > 0.0:
            direction = "up"
            confidence = min(0.5 + abs(ma_distance), 0.95)
        else:
            direction = "down"
            confidence = min(0.5 + abs(ma_distance), 0.95)

        result: dict[str, Judgment] = {}
        for name in questions:
            if name == "direction":
                result[name] = Judgment(
                    name=name,
                    value=direction,
                    confidence=confidence,
                    rationale=f"mean MA distance {ma_distance}",
                )
        return result


def _mean_distance(snapshot: dict) -> float | None:
    distances = snapshot.get("ma_distance") or {}
    values = [v for v in distances.values() if isinstance(v, (int, float))]
    if not values:
        return None
    return sum(values) / len(values)
