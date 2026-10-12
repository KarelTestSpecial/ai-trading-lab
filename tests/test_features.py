"""Feature / state-engine tests."""

from __future__ import annotations

import pytest

from src.features.snapshot import FeatureParams, build_snapshot, realized_volatility
from src.features.state_engine import distance_from_ma, returns, simple_moving_average, zscore
from tests.helpers import make_bars


def test_returns():
    closes = [100.0, 110.0, 121.0]
    assert returns(closes, 1) == pytest.approx(0.1)
    assert returns(closes, 2) == pytest.approx(0.21)
    assert returns([100.0], 1) is None


def test_simple_moving_average():
    assert simple_moving_average([1, 2, 3, 4], 2) == pytest.approx(3.5)
    assert simple_moving_average([1, 2], 3) is None


def test_distance_from_ma():
    assert distance_from_ma([10.0, 20.0], 2) == pytest.approx(20.0 / 15.0 - 1.0)


def test_zscore():
    assert zscore([1.0, 1.0, 1.0], 3) is None  # zero variance
    # population std over [1,2,3] -> (3-2)/sqrt(2/3)
    assert zscore([1.0, 2.0, 3.0], 3) == pytest.approx(1.224744871391589)


def test_realized_volatility_zero_for_constant_growth():
    closes = [100.0 * 1.01**i for i in range(30)]
    assert realized_volatility(closes, 20) == pytest.approx(0.0, abs=1e-9)


def test_build_snapshot_structure():
    bars = make_bars("AAPL", [100.0 + i for i in range(260)])
    snap = build_snapshot("AAPL", bars, FeatureParams())
    assert snap["symbol"] == "AAPL"
    assert snap["close"] == 359.0
    assert set(snap["returns"]) == {"1", "5", "20"}
    assert set(snap["ma_distance"]) == {"20", "50", "200"}
    assert snap["realized_vol"] is not None


def test_build_snapshot_rejects_empty():
    with pytest.raises(ValueError):
        build_snapshot("AAPL", [])
