"""Load the YAML configuration files (universe / strategy / risk).

One owner per fact: the YAML files under `config/` are the source of truth for
the universe, the feature parameters and the hard risk limits. This module turns
them into typed objects so nothing downstream parses raw dicts.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from src.features.snapshot import FeatureParams
from src.policy.risk import RiskLimits

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


class ConfigLoadError(RuntimeError):
    """Raised when a configuration file is missing or malformed."""


@dataclass(frozen=True)
class UniverseConfig:
    symbols: tuple[str, ...]
    benchmark: str


def _load(path: str | Path) -> dict:
    file_path = Path(path)
    if not file_path.exists():
        raise ConfigLoadError(f"config file not found: {file_path}")
    with file_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ConfigLoadError(f"{file_path} must contain a mapping")
    return data


def load_universe(path: str | Path | None = None) -> UniverseConfig:
    data = _load(path or CONFIG_DIR / "universe.yaml")
    symbols = tuple(str(s).upper() for s in data.get("symbols", []))
    if not symbols:
        raise ConfigLoadError("universe must define at least one symbol")
    return UniverseConfig(symbols=symbols, benchmark=str(data.get("benchmark", "SPY")).upper())


def load_strategy(path: str | Path | None = None) -> FeatureParams:
    data = _load(path or CONFIG_DIR / "strategy.yaml")
    features = data.get("features", {})
    return FeatureParams(
        return_windows=tuple(features.get("return_windows", [1, 5, 20])),
        ma_windows=tuple(features.get("ma_windows", [20, 50, 200])),
        vol_window=int(features.get("vol_window", 20)),
        zscore_window=int(features.get("zscore_window", 60)),
    )


def load_risk(path: str | Path | None = None) -> RiskLimits:
    data = _load(path or CONFIG_DIR / "risk.yaml")
    defaults = RiskLimits()
    return RiskLimits(
        max_position_pct=float(data.get("max_position_pct", defaults.max_position_pct)),
        max_daily_loss_pct=float(data.get("max_daily_loss_pct", defaults.max_daily_loss_pct)),
        max_drawdown_pct=float(data.get("max_drawdown_pct", defaults.max_drawdown_pct)),
        max_positions=int(data.get("max_positions", defaults.max_positions)),
        earnings_blackout_days=int(data.get("earnings_blackout_days", defaults.earnings_blackout_days)),
    )
