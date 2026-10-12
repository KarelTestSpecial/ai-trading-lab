"""Application settings and trading-mode resolution.

All safety-relevant configuration lives here so the guardrails are in one place.
"""

from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass
from enum import Enum

# python-dotenv is optional: tests run without it and without a .env file.
if importlib.util.find_spec("dotenv") is not None:
    from dotenv import load_dotenv

    load_dotenv()


class TradingMode(str, Enum):
    PAPER = "paper"
    LIVE = "live"


class ConfigError(RuntimeError):
    """Raised when the environment contains an invalid or unsafe configuration."""


@dataclass(frozen=True)
class Settings:
    trading_mode: TradingMode
    allow_live_trading: bool
    public_demo: bool
    alpaca_api_key: str | None
    alpaca_secret_key: str | None
    alpaca_paper_base_url: str
    alpaca_live_base_url: str
    google_api_key: str | None
    journal_path: str
    # Jev route (arm C). Consumed by cadence-core's JevClient, which only reads
    # these three attributes — duck-typed, so this project keeps its own Settings.
    jev_api_key: str | None
    jev_base_url: str
    jev_model: str

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> Settings:
        env = os.environ if env is None else env

        raw_mode = (env.get("TRADING_MODE") or "paper").strip().lower()
        try:
            mode = TradingMode(raw_mode)
        except ValueError as exc:
            raise ConfigError(
                f"TRADING_MODE must be 'paper' or 'live', got {raw_mode!r}"
            ) from exc

        return cls(
            trading_mode=mode,
            allow_live_trading=_as_bool(env.get("ALLOW_LIVE_TRADING")),
            # Safe default: absent PUBLIC_DEMO is treated as true, so live trading
            # stays impossible unless it is explicitly switched off.
            public_demo=_as_bool(env.get("PUBLIC_DEMO", "true")),
            alpaca_api_key=env.get("ALPACA_API_KEY") or None,
            alpaca_secret_key=env.get("ALPACA_SECRET_KEY") or None,
            alpaca_paper_base_url=env.get("ALPACA_PAPER_BASE_URL")
            or "https://paper-api.alpaca.markets",
            alpaca_live_base_url=env.get("ALPACA_LIVE_BASE_URL") or "https://api.alpaca.markets",
            google_api_key=env.get("GOOGLE_API_KEY") or None,
            # Committed location: the daily Action appends here and pushes, so the
            # public git history becomes a tamper-evident track record.
            journal_path=env.get("JOURNAL_PATH") or "journal/decisions.jsonl",
            jev_api_key=env.get("JEV_API_KEY") or None,
            jev_base_url=env.get("JEV_BASE_URL") or "https://api.typesafe.ai",
            jev_model=env.get("JEV_MODEL") or "jev",
        )


def _as_bool(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def load_settings(env: dict[str, str] | None = None) -> Settings:
    return Settings.from_env(env)
