"""
Backtest harness: run strategy against historical bars.
"""
from __future__ import annotations

import pandas as pd

from ibkr_quant.backtest.portfolio import Portfolio
from ibkr_quant.config import IndicatorSettings, StrategySettings
from ibkr_quant.indicators import add_indicators
from ibkr_quant.logging_setup import get_logger
from ibkr_quant.models import Regime, Side, SignalDirection
from ibkr_quant.strategy import build_setups, run_setups, score_signal

logger = get_logger("backtest")


class BacktestHarness:
    def __init__(
        self,
        initial_cash: float = 100_000.0,
        position_size_pct: float = 0.03,
        risk_per_trade: float = 0.02,
    ) -> None:
        self.initial_cash = initial_cash
        self.position_size_pct = position_size_pct
        self.risk_per_trade = risk_per_trade
        self.portfolio = Portfolio(initial_cash)

    def run(
        self,
        bars: dict[str, pd.DataFrame],
        indicators: IndicatorSettings,
        strategy: StrategySettings,
    ) -> Portfolio:
        logger.info("Starting backtest for %d symbols", len(bars))
        setups = build_setups(indicators, strategy)

        all_dates = sorted(
            set().union(*[set(df["date"]) for df in bars.values() if "date" in df.columns])
        )

        for sig_date in all_dates:
            for symbol, df in bars.items():
                if sig_date not in df["date"].values:
                    continue

                idx = df[df["date"] == sig_date].index[0]
                if idx < 200:
                    continue

                df_sym = df.copy()
                signals = run_setups(df_sym, setups, indicators)

                for sig in signals:
                    if sig.symbol != symbol:
                        continue

                    qty = (self.initial_cash * self.position_size_pct) / sig.entry_price
                    qty = float(int(qty / 100) * 100)

                    stop = sig.entry_price - sig.stop_distance_atr
                    target = sig.entry_price + (sig.stop_distance_atr * 2)

                    self.portfolio.open_position(
                        symbol=symbol,
                        side=Side(sig.direction.value),
                        qty=qty,
                        entry_date=sig_date,
                        entry_price=sig.entry_price,
                        stop_price=stop,
                        target_price=target,
                    )

                    logger.debug(
                        "Backtest: opened %s %s @ %.2f stop=%.2f target=%.2f",
                        sig.direction.value,
                        symbol,
                        sig.entry_price,
                        stop,
                        target,
                    )

        logger.info(
            "Backtest complete: %d positions opened, %d closed",
            len(self.portfolio.positions),
            len(self.portfolio.closed),
        )
        return self.portfolio
