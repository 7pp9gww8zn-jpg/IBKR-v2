"""
Backtest report: metrics, equity curve, trade analysis.
"""
from __future__ import annotations

import pandas as pd

from ibkr_quant.backtest.portfolio import Portfolio


class BacktestReport:
    def __init__(self, portfolio: Portfolio) -> None:
        self.portfolio = portfolio

    def summary(self) -> dict:
        closed = self.portfolio.closed
        if not closed:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "avg_pnl": 0.0,
                "total_pnl": 0.0,
            }

        total_pnl = sum(p.pnl for p in closed)
        winning = [p for p in closed if p.pnl > 0]
        losing = [p for p in closed if p.pnl <= 0]

        return {
            "total_trades": len(closed),
            "winning_trades": len(winning),
            "losing_trades": len(losing),
            "win_rate": len(winning) / len(closed) if closed else 0,
            "avg_pnl": total_pnl / len(closed) if closed else 0,
            "total_pnl": total_pnl,
        }

    def equity_curve(self) -> pd.DataFrame:
        return self.portfolio.equity_curve_dataframe()

    def trades(self) -> pd.DataFrame:
        return self.portfolio.to_dataframe()

    def print_summary(self) -> None:
        s = self.summary()
        print("=== Backtest Summary ===")
        print(f"Total trades:      {s['total_trades']}")
        print(f"Winning trades:    {s['winning_trades']}")
        print(f"Losing trades:     {s['losing_trades']}")
        print(f"Win rate:          {s['win_rate']:.1%}")
        print(f"Average P&L:      ${s['avg_pnl']:.2f}")
        print(f"Total P&L:        ${s['total_pnl']:.2f}")
