"""
Technical indicator computations — pure pandas/numpy functions.
No side effects, no IBKR calls, no async.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def ema(series: pd.Series, n: int) -> pd.Series:
    return series.ewm(span=n, adjust=False).mean()


def sma(series: pd.Series, n: int) -> pd.Series:
    return series.rolling(window=n).mean()


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / n, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / n, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def macd(
    close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[pd.Series, pd.Series, pd.Series]:
    ema_fast_val = ema(close, fast)
    ema_slow_val = ema(close, slow)
    macd_line = ema_fast_val - ema_slow_val
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def atr(
    high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14
) -> pd.Series:
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr_val = tr.ewm(alpha=1 / n, adjust=False).mean()
    return atr_val


def adx(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14) -> pd.Series:
    plus_dm = high.diff()
    minus_dm = (-low).diff()
    plus_dm = plus_dm.where(plus_dm > minus_dm, 0.0).where(plus_dm > 0, 0.0)
    minus_dm = minus_dm.where(minus_dm > plus_dm, 0.0).where(minus_dm > 0, 0.0)
    tr = pd.concat(
        [high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()],
        axis=1,
    ).max(axis=1)
    atr_val = atr(high, low, close, n)
    plus_di = 100 * (plus_dm.ewm(alpha=1 / n, adjust=False).mean() / atr_val)
    minus_di = 100 * (minus_dm.ewm(alpha=1 / n, adjust=False).mean() / atr_val)
    dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di))
    adx_val = dx.ewm(alpha=1 / n, adjust=False).mean()
    return adx_val


def add_indicators(
    df: pd.DataFrame,
    ema_fast: int = 20,
    ema_slow: int = 40,
    sma_mid_fast: int = 50,
    sma_mid_slow: int = 100,
    sma_long_fast: int = 100,
    sma_long_slow: int = 200,
    rsi_period: int = 14,
    macd_fast: int = 12,
    macd_slow: int = 26,
    macd_signal: int = 9,
    atr_period: int = 14,
    adx_period: int = 14,
) -> pd.DataFrame:
    out = df.copy()
    out["ema_fast"] = ema(out["close"], ema_fast)
    out["ema_slow"] = ema(out["close"], ema_slow)
    out["sma_mid_fast"] = sma(out["close"], sma_mid_fast)
    out["sma_mid_slow"] = sma(out["close"], sma_mid_slow)
    out["sma_long_fast"] = sma(out["close"], sma_long_fast)
    out["sma_long_slow"] = sma(out["close"], sma_long_slow)
    out["rsi"] = rsi(out["close"], rsi_period)
    macd_line, signal_line, hist = macd(
        out["close"], macd_fast, macd_slow, macd_signal
    )
    out["macd_line"] = macd_line
    out["macd_signal"] = signal_line
    out["macd_hist"] = hist
    out["atr"] = atr(out["high"], out["low"], out["close"], atr_period)
    out["adx"] = adx(out["high"], out["low"], out["close"], adx_period)
    out["volume_ma20"] = sma(out["volume"], 20)
    out["relative_volume"] = out["volume"] / out["volume_ma20"]
    return out
