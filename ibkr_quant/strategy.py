"""
Trend-following momentum strategy: regime classification, setup detection, signal scoring.
"""
from __future__ import annotations

from typing import Sequence

import pandas as pd

from ibkr_quant.config import IndicatorSettings, StrategySettings
from ibkr_quant.indicators import add_indicators
from ibkr_quant.logging_setup import get_logger
from ibkr_quant.models import (
    Regime,
    Side,
    SignalCore,
    SignalDirection,
)

logger = get_logger("strategy")


def classify_regime(
    df: pd.DataFrame,
    ind: IndicatorSettings,
) -> Regime:
    row = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else row

    ema_fast = row.get("ema_fast")
    ema_slow = row.get("ema_slow")
    sma_mid_slow = row.get("sma_mid_slow")
    sma_long_slow = row.get("sma_long_slow")
    rsi_val = row.get("rsi")
    adx_val = row.get("adx")
    macd_hist = row.get("macd_hist")

    if any(pd.isna([ema_fast, ema_slow, sma_mid_slow, sma_long_slow])):
        return Regime.UNKNOWN

    price = row["close"]

    uptrend = (
        ema_fast > ema_slow
        and sma_mid_slow > sma_long_slow
        and price > ema_fast
    )
    downtrend = (
        ema_fast < ema_slow
        and sma_mid_slow < sma_long_slow
        and price < ema_fast
    )

    if uptrend:
        if adx_val is not None and adx_val > 25 and macd_hist is not None and macd_hist > 0:
            return Regime.UPTREND
        return Regime.UPTREND

    if downtrend:
        if adx_val is not None and adx_val > 25 and macd_hist is not None and macd_hist < 0:
            return Regime.DOWNTREND
        return Regime.DOWNTREND

    if adx_val is not None and adx_val < 15:
        return Regime.CONSOLIDATION

    if rsi_val is not None:
        if rsi_val < 35 and macd_hist is not None and macd_hist > 0:
            return Regime.REVERSAL_BULL
        if rsi_val > 65 and macd_hist is not None and macd_hist < 0:
            return Regime.REVERSAL_BEAR

    return Regime.UNKNOWN


class Setup:
    name: str = ""
    direction: SignalDirection = SignalDirection.LONG

    def filter(self, df: pd.DataFrame, ind: IndicatorSettings, strat: StrategySettings) -> bool:
        raise NotImplementedError

    def signal_from(self, df: pd.DataFrame, ind: IndicatorSettings) -> SignalCore | None:
        raise NotImplementedError


class UptrendPullbackLong(Setup):
    name = "UptrendPullbackLong"
    direction = SignalDirection.LONG

    def filter(self, df: pd.DataFrame, ind: IndicatorSettings, strat: StrategySettings) -> bool:
        row = df.iloc[-1]
        prev = df.iloc[-2] if len(df) >= 2 else row

        ema_fast = row.get("ema_fast")
        ema_slow = row.get("ema_slow")
        rsi_val = row.get("rsi")
        sma_mid_fast = row.get("sma_mid_fast")
        sma_long_fast = row.get("sma_long_fast")

        if any(pd.isna([ema_fast, ema_slow, rsi_val, sma_mid_fast, sma_long_fast])):
            return False

        trend = ema_fast > ema_slow and sma_mid_fast > sma_long_fast
        pullback = strat.rsi_long_min <= rsi_val <= strat.rsi_long_max
        close_above_ema = row["close"] > ema_fast

        return trend and pullback and close_above_ema

    def signal_from(self, df: pd.DataFrame, ind: IndicatorSettings) -> SignalCore | None:
        row = df.iloc[-1]
        return SignalCore(
            symbol=row["symbol"] if "symbol" in row else "",
            direction=self.direction,
            regime=Regime.UPTREND,
            setup_name=self.name,
            entry_price=0.0,
            stop_distance_atr=row.get("atr", 1.0),
            rsi=row.get("rsi", 50.0),
            macd_hist=row.get("macd_hist", 0.0),
            atr=row.get("atr", 1.0),
            relative_volume=row.get("relative_volume", 1.0),
        )


class DowntrendBounceShort(Setup):
    name = "DowntrendBounceShort"
    direction = SignalDirection.SHORT

    def filter(self, df: pd.DataFrame, ind: IndicatorSettings, strat: StrategySettings) -> bool:
        row = df.iloc[-1]

        ema_fast = row.get("ema_fast")
        ema_slow = row.get("ema_slow")
        rsi_val = row.get("rsi")
        sma_mid_fast = row.get("sma_mid_fast")
        sma_long_fast = row.get("sma_long_fast")

        if any(pd.isna([ema_fast, ema_slow, rsi_val, sma_mid_fast, sma_long_fast])):
            return False

        trend = ema_fast < ema_slow and sma_mid_fast < sma_long_fast
        bounce = strat.rsi_short_min <= rsi_val <= strat.rsi_short_max
        close_below_ema = row["close"] < ema_fast

        return trend and bounce and close_below_ema

    def signal_from(self, df: pd.DataFrame, ind: IndicatorSettings) -> SignalCore | None:
        row = df.iloc[-1]
        return SignalCore(
            symbol=row["symbol"] if "symbol" in row else "",
            direction=self.direction,
            regime=Regime.DOWNTREND,
            setup_name=self.name,
            entry_price=0.0,
            stop_distance_atr=row.get("atr", 1.0),
            rsi=row.get("rsi", 50.0),
            macd_hist=row.get("macd_hist", 0.0),
            atr=row.get("atr", 1.0),
            relative_volume=row.get("relative_volume", 1.0),
        )


class BullishReversalLong(Setup):
    name = "BullishReversalLong"
    direction = SignalDirection.LONG

    def filter(self, df: pd.DataFrame, ind: IndicatorSettings, strat: StrategySettings) -> bool:
        if len(df) < strat.reversal_lookback_bars + 1:
            return False

        row = df.iloc[-1]
        lookback = df.iloc[-strat.reversal_lookback_bars - 1 :]

        rsi_val = row.get("rsi")
        macd_hist = row.get("macd_hist")
        adx_val = row.get("adx")

        if any(pd.isna([rsi_val, macd_hist])):
            return False

        RSI_OVERSOLD = 40.0
        oversold = rsi_val < RSI_OVERSOLD
        macd_turning_up = macd_hist > 0

        recent_low = lookback["low"].min()
        at_support = row["low"] <= recent_low * 1.02

        return oversold and macd_turning_up and at_support

    def signal_from(self, df: pd.DataFrame, ind: IndicatorSettings) -> SignalCore | None:
        row = df.iloc[-1]
        return SignalCore(
            symbol=row["symbol"] if "symbol" in row else "",
            direction=self.direction,
            regime=Regime.REVERSAL_BULL,
            setup_name=self.name,
            entry_price=0.0,
            stop_distance_atr=row.get("atr", 1.0),
            rsi=row.get("rsi", 50.0),
            macd_hist=row.get("macd_hist", 0.0),
            atr=row.get("atr", 1.0),
            relative_volume=row.get("relative_volume", 1.0),
        )


class BearishReversalShort(Setup):
    name = "BearishReversalShort"
    direction = SignalDirection.SHORT

    def filter(self, df: pd.DataFrame, ind: IndicatorSettings, strat: StrategySettings) -> bool:
        if len(df) < strat.reversal_lookback_bars + 1:
            return False

        row = df.iloc[-1]
        lookback = df.iloc[-strat.reversal_lookback_bars - 1 :]

        rsi_val = row.get("rsi")
        macd_hist = row.get("macd_hist")

        if any(pd.isna([rsi_val, macd_hist])):
            return False

        RSI_OVERBOUGHT = 60.0
        overbought = rsi_val > RSI_OVERBOUGHT
        macd_turning_down = macd_hist < 0

        recent_high = lookback["high"].max()
        at_resistance = row["high"] >= recent_high * 0.98

        return overbought and macd_turning_down and at_resistance

    def signal_from(self, df: pd.DataFrame, ind: IndicatorSettings) -> SignalCore | None:
        row = df.iloc[-1]
        return SignalCore(
            symbol=row["symbol"] if "symbol" in row else "",
            direction=self.direction,
            regime=Regime.REVERSAL_BEAR,
            setup_name=self.name,
            entry_price=0.0,
            stop_distance_atr=row.get("atr", 1.0),
            rsi=row.get("rsi", 50.0),
            macd_hist=row.get("macd_hist", 0.0),
            atr=row.get("atr", 1.0),
            relative_volume=row.get("relative_volume", 1.0),
        )


class ConsolidationBreakout(Setup):
    name = "ConsolidationBreakout"
    direction = SignalDirection.LONG

    def filter(self, df: pd.DataFrame, ind: IndicatorSettings, strat: StrategySettings) -> bool:
        if len(df) < 20:
            return False

        row = df.iloc[-1]
        lookback = df.iloc[-20:]

        rsi_val = row.get("rsi")
        adx_val = row.get("adx")
        macd_hist = row.get("macd_hist")

        if any(pd.isna([rsi_val, adx_val, macd_hist])):
            return False

        consolidate = adx_val < strat.adx_consolidation_max
        tight_range = (lookback["high"].max() - lookback["low"].min()) / lookback["low"].min() < 0.05
        breakout = macd_hist > 0 and rsi_val > 50

        return consolidate and tight_range and breakout

    def signal_from(self, df: pd.DataFrame, ind: IndicatorSettings) -> SignalCore | None:
        row = df.iloc[-1]
        return SignalCore(
            symbol=row["symbol"] if "symbol" in row else "",
            direction=self.direction,
            regime=Regime.CONSOLIDATION,
            setup_name=self.name,
            entry_price=0.0,
            stop_distance_atr=row.get("atr", 1.0),
            rsi=row.get("rsi", 50.0),
            macd_hist=row.get("macd_hist", 0.0),
            atr=row.get("atr", 1.0),
            relative_volume=row.get("relative_volume", 1.0),
        )


def build_setups(
    ind: IndicatorSettings,
    strat: StrategySettings,
) -> list[Setup]:
    enabled = set(strat.enabled_setups)
    all_setups: list[Setup] = [
        UptrendPullbackLong(),
        DowntrendBounceShort(),
        BullishReversalLong(),
        BearishReversalShort(),
        ConsolidationBreakout(),
    ]
    return [s for s in all_setups if s.name in enabled]


def run_setups(
    df: pd.DataFrame,
    setups: Sequence[Setup],
    ind: IndicatorSettings,
) -> list[SignalCore]:
    df = df.copy()
    df = add_indicators(
        df,
        ema_fast=ind.ema_fast,
        ema_slow=ind.ema_slow,
        sma_mid_fast=ind.sma_mid_fast,
        sma_mid_slow=ind.sma_mid_slow,
        sma_long_fast=ind.sma_long_fast,
        sma_long_slow=ind.sma_long_slow,
        rsi_period=ind.rsi_period,
        macd_fast=ind.macd_fast,
        macd_slow=ind.macd_slow,
        macd_signal=ind.macd_signal,
        atr_period=ind.atr_period,
        adx_period=ind.adx_period,
    )

    signals: list[SignalCore] = []
    for s in setups:
        try:
            if s.filter(df, ind, settings := object):  # type: ignore[assignment]
                sig = s.signal_from(df, ind)
                if sig:
                    sig.score = score_signal(sig)
                    signals.append(sig)
        except Exception:
            continue

    return signals


def score_signal(sig: SignalCore) -> float:
    score = 0.0

    if sig.direction == SignalDirection.LONG:
        if 45 <= sig.rsi <= 65:
            score += 25
        elif sig.rsi < 45:
            score += 15
        if sig.macd_hist > 0:
            score += 25
        if sig.relative_volume > 1.2:
            score += 20
        if sig.atr > 0:
            score += 15
    else:
        if 35 <= sig.rsi <= 55:
            score += 25
        elif sig.rsi > 55:
            score += 15
        if sig.macd_hist < 0:
            score += 25
        if sig.relative_volume > 1.2:
            score += 20
        if sig.atr > 0:
            score += 15

    return score
