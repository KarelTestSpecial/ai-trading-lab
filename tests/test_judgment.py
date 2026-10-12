"""Judgment-layer tests (offline: parsing, clients, adapters)."""

from __future__ import annotations

import json

import pytest

from src.judgment.base import Judgment, JudgmentError
from src.judgment.client import StaticLLMClient
from src.judgment.gemini import GeminiClient, extract_text
from src.judgment.jev import JevAdapter, JevUnavailableError
from src.judgment.llm import DEFAULT_QUESTIONS, LLMJudge, parse_judgments
from src.judgment.rules import RuleBasedJudge

VALID = json.dumps({"direction": {"value": "up", "confidence": 0.7, "rationale": "trend"}})


def test_parse_valid():
    judgments = parse_judgments(VALID, DEFAULT_QUESTIONS)
    assert judgments["direction"].value == "up"
    assert judgments["direction"].confidence == 0.7


def test_parse_strips_code_fences():
    fenced = f"```json\n{VALID}\n```"
    assert parse_judgments(fenced, DEFAULT_QUESTIONS)["direction"].value == "up"


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        json.dumps({"direction": {"value": "sideways", "confidence": 0.5}}),
        json.dumps({"direction": {"value": "up", "confidence": 1.5}}),
        json.dumps({"direction": {"value": "up", "confidence": "high"}}),
        json.dumps({}),
    ],
)
def test_parse_rejects_bad_payloads(raw):
    with pytest.raises(JudgmentError):
        parse_judgments(raw, DEFAULT_QUESTIONS)


def test_llm_judge_uses_client():
    client = StaticLLMClient(VALID)
    judge = LLMJudge(client)
    result = judge.judge({"symbol": "AAPL"}, DEFAULT_QUESTIONS)
    assert result["direction"].value == "up"
    assert "AAPL" in client.prompts[0]


def test_jev_adapter_is_explicit_stub():
    with pytest.raises(JevUnavailableError):
        JevAdapter().judge({"symbol": "AAPL"}, DEFAULT_QUESTIONS)


def test_jev_adapter_with_predict():
    def predict(snapshot):
        return {"direction": Judgment("direction", "down", 0.6)}

    result = JevAdapter(predict).judge({"symbol": "AAPL"}, DEFAULT_QUESTIONS)
    assert result["direction"].value == "down"


def test_rule_based_judge_up_and_down():
    up = RuleBasedJudge().judge({"ma_distance": {"20": 0.05, "50": 0.03}}, DEFAULT_QUESTIONS)
    down = RuleBasedJudge().judge({"ma_distance": {"20": -0.05}}, DEFAULT_QUESTIONS)
    assert up["direction"].value == "up"
    assert down["direction"].value == "down"


def test_gemini_client_requires_key():
    with pytest.raises(JudgmentError):
        GeminiClient(None)


def test_extract_text_parses_and_rejects():
    payload = {"candidates": [{"content": {"parts": [{"text": "hello"}]}}]}
    assert extract_text(payload) == "hello"
    with pytest.raises(JudgmentError):
        extract_text({"unexpected": True})
