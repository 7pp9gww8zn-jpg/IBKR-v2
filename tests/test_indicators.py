"""
Tests for technical indicators.
"""
import numpy as np
import pandas as pd
import pytest

from ibkr_quant.indicators import add_indicators, atr, ema, macd, rsi, sma


class TestEMA:
    def test_ema_length(self):
        s = pd.Series([1.0] * 50)
        result = ema(s, 20)
        assert len(result) == 50
        assert result.notna().sum() == 50

    def test_ema_smoothing(self):
        s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        result = ema(s, 3)
        assert result.iloc[-1] == pytest.approx(4.0, rel=0.1)


class TestSMA:
    def test_sma_basic(self):
        s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        result = sma(s, 3)
        assert result.iloc[-1] == 4.0
        assert result.iloc[0] is pd.NA

    def test_sma_short(self):
        s = pd.Series([10.0] * 10)
        result = sma(s, 5)
        assert result.notna().sum() == 10
        assert (result.dropna() == 10.0).all()


class TestRSI:
    def test_rsi_bounds(self):
        close = pd.Series([100.0 + np.random.randn() * 0.5 for _ in range(100)])
        result = rsi(close, 14)
        valid = result.dropna()
        assert (valid >= 0).all()
        assert (valid <= 100).all()

    def test_rsi_all_gains(self):
        close = pd.Series(np.linspace(100, 120, 50))
        result = rsi(close, 14)
        assert result.iloc[-1] > 50

    def test_rsi_all_losses(self):
        close = pd.Series(np.linspace(120, 100, 50))
        result = rsi(close, 14)
        assert result.iloc[-1] < 50


class TestMACD:
    def test_macd_returns_tuple(self):
        close = pd.Series([100.0] * 50)
        macd_line, signal, hist = macd(close)
        assert len(macd_line) == 50
        assert len(signal) == 50
        assert len(hist) == 50

    def test_macd_hist_sign(self):
        close = pd.Series(np.linspace(100, 110, 60))
        _, _, hist = macd(close)
        assert hist.iloc[-1] > 0


class TestATR:
    def test_atr_positive(self):
        high = pd.Series([105, 110, 108, 112, 115])
        low = pd.Series([95, 100, 97, 102, 105])
        close = pd.Series([100, 105, 103, 108, 111])
        result = atr(high, low, close, 14)
        assert result.notna().any()
        assert (result >= 0).all()


class TestAddIndicators:
    def test_all_columns_present(self):
        dates = pd.date_range("2020-01-01", periods=300, freq="D")
        df = pd.DataFrame(
            {
                "date": dates,
                "open": 100 + np.random.randn(300) * 0.5,
                "high": 101 + np.random.randn(300) * 0.5,
                "low": 99 + np.random.randn(300) * 0.5,
                "close": 100 + np.random.randn(300) * 0.5,
                "volume": 1_000_000 + np.random.randn(300) * 50000,
            }
        )
        result = add_indicators(df)
        expected = [
            "ema_fast",
            "ema_slow",
            "sma_mid_fast",
            "sma_mid_slow",
            "sma_long_fast",
            "sma_long_slow",
            "rsi",
            "macd_line",
            "macd_signal",
            "macd_hist",
            "atr",
            "adx",
            "volume_ma20",
            "relative_volume",
        ]
        for col in expected:
            assert col in result.columns, f"Missing column: {col}"

    def test_indicators_after_200_bars(self):
        dates = pd.date_range("2020-01-01", periods=300, freq="D")
        df = pd.DataFrame(
            {
                "date": dates,
                "open": 100 + np.random.randn(300) * 0.5,
                "high": 101 + np.random.randn(300) * 0.5,
                "low": 99 + np.random.randn(300) * 0.5,
                "close": 100 + np.random.randn(300) * 0.5,
                "volume": 1_000_000 + np.random.randn(300) * 50000,
            }
        )
        result = add_indicators(df)
        row_200 = result.iloc[199]
        assert not pd.isna(row_200["sma_long_slow"])
        assert not pd.isna(row_200["rsi"])
        assert not pd.isna(row_200["macd_hist"])
