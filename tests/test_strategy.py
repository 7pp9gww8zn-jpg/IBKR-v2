"""
Tests for regime classification and setup detection.
"""
import numpy as np
import pandas as pd
import pytest

from ibkr_quant.config import IndicatorSettings, StrategySettings
from ibkr_quant.indicators import add_indicators
from ibkr_quant.models import Regime, SignalDirection
from ibkr_quant.strategy import (
    UptrendPullbackLong,
    DowntrendBounceShort,
    BullishReversalLong,
    BearishReversalShort,
    ConsolidationBreakout,
    classify_regime,
    score_signal,
    build_setups,
    run_setups,
)
from ibkr_quant.models import SignalCore


def _make_bars(
    trend: str = "uptrend", n: int = 250, start_price: float = 100.0
) -> pd.DataFrame:
    np.random.seed(42)
    dates = pd.date_range("2020-01-01", periods=n, freq="D")
    price = start_price
    if trend == "uptrend":
        close = [price := price * (1 + 0.001 + np.random.randn() * 0.005) for _ in range(n)]
    elif trend == "downtrend":
        close = [price := price * (1 - 0.001 + np.random.randn() * 0.005) for _ in range(n)]
    elif trend == "reversal_bull":
        close = []
        for i in range(n):
            if i < n // 2:
                close.append(price := price * (1 - 0.001 + np.random.randn() * 0.005))
            else:
                close.append(price := price * (1 + 0.002 + np.random.randn() * 0.005))
    else:
        close = [price := price + np.sin(i / 20) * 0.5 + np.random.randn() * 0.3 for i in range(n)]

    open_ = close
    high = [c * (1 + abs(np.random.randn() * 0.002)) for c in close]
    low = [c * (1 - abs(np.random.randn() * 0.002)) for c in close]
    volume = [1_000_000 + np.random.randn() * 50000 for _ in close]

    return pd.DataFrame(
        {"date": dates, "open": open_, "high": high, "low": low, "close": close, "volume": volume}
    )


def _add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    return add_indicators(df)


class TestRegimeClassification:
    def test_uptrend_regime(self):
        df = _make_bars("uptrend")
        df = _add_indicators(df)
        regime = classify_regime(df, IndicatorSettings())
        assert regime == Regime.UPTREND

    def test_downtrend_regime(self):
        df = _make_bars("downtrend")
        df = _add_indicators(df)
        regime = classify_regime(df, IndicatorSettings())
        assert regime == Regime.DOWNTREND

    def test_consolidation_regime(self):
        df = _make_bars("neutral")
        df = _add_indicators(df)
        regime = classify_regime(df, IndicatorSettings())
        assert regime == Regime.CONSOLIDATION


class TestUptrendPullbackLong:
    def setup_method(self):
        self.s = UptrendPullbackLong()
        self.ind = IndicatorSettings()
        self.strat = StrategySettings()

    def test_filter_uptrend_pullback(self):
        df = _make_bars("uptrend")
        df = _add_indicators(df)
        assert self.s.filter(df, self.ind, self.strat)

    def test_filter_no_signal_in_downtrend(self):
        df = _make_bars("downtrend")
        df = _add_indicators(df)
        assert not self.s.filter(df, self.ind, self.strat)


class TestDowntrendBounceShort:
    def setup_method(self):
        self.s = DowntrendBounceShort()
        self.ind = IndicatorSettings()
        self.strat = StrategySettings()

    def test_filter_downtrend_bounce(self):
        df = _make_bars("downtrend")
        df = _add_indicators(df)
        assert self.s.filter(df, self.ind, self.strat)


class TestBullishReversalLong:
    def setup_method(self):
        self.s = BullishReversalLong()
        self.ind = IndicatorSettings()
        self.strat = StrategySettings()

    def test_filter_reversal_bull(self):
        df = _make_bars("reversal_bull")
        df = _add_indicators(df)
        result = self.s.filter(df, self.ind, self.strat)
        assert isinstance(result, bool)


class TestBearishReversalShort:
    def setup_method(self):
        self.s = BearishReversalShort()
        self.ind = IndicatorSettings()
        self.strat = StrategySettings()

    def test_filter_reversal_bear(self):
        df = _make_bars("reversal_bull")
        df = _add_indicators(df)
        result = self.s.filter(df, self.ind, self.strat)
        assert isinstance(result, bool)


class TestBuildSetups:
    def test_build_setups_filters_by_enabled(self):
        ind = IndicatorSettings()
        strat = StrategySettings(enabled_setups=["UptrendPullbackLong"])
        setups = build_setups(ind, strat)
        assert len(setups) == 1
        assert setups[0].name == "UptrendPullbackLong"

    def test_build_setups_all_enabled(self):
        ind = IndicatorSettings()
        strat = StrategySettings(
            enabled_setups=[
                "UptrendPullbackLong",
                "DowntrendBounceShort",
                "BullishReversalLong",
                "BearishReversalShort",
                "ConsolidationBreakout",
            ]
        )
        setups = build_setups(ind, strat)
        assert len(setups) == 5


class TestRunSetups:
    def test_run_setups_returns_signals(self):
        df = _make_bars("uptrend")
        df = _add_indicators(df)
        ind = IndicatorSettings()
        strat = StrategySettings(
            enabled_setups=[
                "UptrendPullbackLong",
                "DowntrendBounceShort",
            ]
        )
        setups = build_setups(ind, strat)
        signals = run_setups(df, setups, ind)
        assert isinstance(signals, list)


class TestScoreSignal:
    def test_score_long_positive_momentum(self):
        sig = SignalCore(
            symbol="TEST",
            direction=SignalDirection.LONG,
            regime=Regime.UPTREND,
            setup_name="Test",
            entry_price=100.0,
            stop_distance_atr=2.0,
            rsi=55.0,
            macd_hist=1.0,
            atr=2.0,
            relative_volume=1.5,
            score=0.0,
        )
        scored = score_signal(sig)
        assert scored > 0

    def test_score_short_positive_momentum(self):
        sig = SignalCore(
            symbol="TEST",
            direction=SignalDirection.SHORT,
            regime=Regime.DOWNTREND,
            setup_name="Test",
            entry_price=100.0,
            stop_distance_atr=2.0,
            rsi=45.0,
            macd_hist=-1.0,
            atr=2.0,
            relative_volume=1.5,
            score=0.0,
        )
        scored = score_signal(sig)
        assert scored > 0
