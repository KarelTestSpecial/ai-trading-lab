"""LLM judgment model (arm B).

Builds a strict, JSON-only prompt from a state snapshot plus optional context,
then parses the model's answer into typed `Judgment`s. The parser is defensive:
anything that is not a valid, in-range judgment raises `JudgmentError`, so a
malformed model answer can never silently become a trade.
"""

from __future__ import annotations

import json

from cadence_core.judgment.base import Judgment, JudgmentError, JudgmentModel

from src.judgment.client import LLMClient

DEFAULT_QUESTIONS: dict[str, list[str]] = {"direction": ["up", "down", "flat"]}

SYSTEM_PROMPT = (
    "You are a disciplined, well-calibrated equity analyst. You answer atomic "
    "questions about ONE stock using only the provided data. You never invent "
    "facts. You return strict JSON and nothing else."
)


def build_prompt(snapshot: dict, questions: dict, context: str | None = None) -> str:
    question_lines = "\n".join(
        f'- "{name}": one of {values}' for name, values in questions.items()
    )
    return (
        "STATE SNAPSHOT (numbers computed elsewhere; do not recompute):\n"
        f"{json.dumps(snapshot, sort_keys=True)}\n\n"
        f"CONTEXT:\n{context or '(none)'}\n\n"
        "QUESTIONS:\n"
        f"{question_lines}\n\n"
        "For each question choose exactly one allowed value and give a CALIBRATED "
        "probability in [0,1] that your chosen value is correct, plus a one-sentence "
        "rationale.\n"
        'Return strict JSON only: {"<question>": {"value": "...", "confidence": 0.0, '
        '"rationale": "..."}}'
    )


def _strip_fences(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    return text.strip()


def parse_judgments(raw: str, questions: dict) -> dict[str, Judgment]:
    try:
        data = json.loads(_strip_fences(raw))
    except json.JSONDecodeError as exc:
        raise JudgmentError(f"model did not return valid JSON: {raw[:200]!r}") from exc
    if not isinstance(data, dict):
        raise JudgmentError("model response must be a JSON object")

    judgments: dict[str, Judgment] = {}
    for name, allowed in questions.items():
        entry = data.get(name)
        if not isinstance(entry, dict):
            raise JudgmentError(f"missing judgment for question {name!r}")
        value = entry.get("value")
        if value not in allowed:
            raise JudgmentError(f"value {value!r} for {name!r} not in {allowed}")
        try:
            confidence = float(entry.get("confidence"))
        except (TypeError, ValueError) as exc:
            raise JudgmentError(f"confidence for {name!r} is not a number") from exc
        if not 0.0 <= confidence <= 1.0:
            raise JudgmentError(f"confidence for {name!r} out of range: {confidence}")
        judgments[name] = Judgment(
            name=name,
            value=value,
            confidence=confidence,
            rationale=str(entry.get("rationale", "")),
        )
    return judgments


class LLMJudge(JudgmentModel):
    def __init__(self, client: LLMClient, *, questions: dict | None = None) -> None:
        self.client = client
        self.questions = questions or DEFAULT_QUESTIONS

    def judge(self, snapshot: dict, questions: dict | None = None) -> dict[str, Judgment]:
        active = questions or self.questions
        context = snapshot.get("context") if isinstance(snapshot, dict) else None
        prompt = build_prompt(snapshot, active, context=context)
        raw = self.client.complete(prompt, system=SYSTEM_PROMPT)
        return parse_judgments(raw, active)
