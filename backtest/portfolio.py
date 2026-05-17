"""
Backtest portfolio: positions, equity curve, metrics.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import pandas as pd

from ibkr_quant.models import Position, PositionStatus, Side


@dataclass
class BacktestPosition:
    symbol: str
    side: Side
    qty: float
    entry_date: date
    entry_price: float
    stop_price: float
    target_price: float
    exit_date: Optional[date] = None
    exit_price: Optional[float] = None
    pnl: float = 0.0
    return_pct: float = 0.0


class Portfolio:
    def __init__(self, initial_cash: float = 100_000.0) -> None:
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.positions: list[BacktestPosition] = []
        self.closed: list[BacktestPosition] = []
        self.equity_curve: list[dict] = []

    def open_position(
        self,
        symbol: str,
        side: Side,
        qty: float,
        entry_date: date,
        entry_price: float,
        stop_price: float,
        target_price: float,
    ) -> None:
        self.positions.append(
            BacktestPosition(
                symbol=symbol,
                side=side,
                qty=qty,
                entry_date=entry_date,
                entry_price=entry_price,
                stop_price=stop_price,
                target_price=target_price,
            )
        )

    def close_position(self, symbol: str, exit_date: date, exit_price: float) -> None:
        for pos in self.positions:
            if pos.symbol == symbol:
                pos.exit_date = exit_date
                pos.exit_price = exit_price
                if pos.side == Side.LONG:
                    pos.pnl = (exit_price - pos.entry_price) * pos.qty
                else:
                    pos.pnl = (pos.entry_price - exit_price) * pos.qty
                pos.return_pct = pos.pnl / (pos.entry_price * pos.qty)
                self.closed.append(pos)
                self.positions.remove(pos)
                return

    def update_equity(self, date: date, portfolio_value: float) -> None:
        self.equity_curve.append({"date": date, "value": portfolio_value})

    def total_equity(self) -> float:
        pos_value = sum(
            p.exit_price * p.qty if p.exit_price else p.entry_price * p.qty
            for p in self.closed
        )
        return self.cash + sum(p.entry_price * p.qty for p in self.positions) + sum(p.pnl for p in self.closed)

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame([
            {
                "symbol": p.symbol,
                "side": p.side.value,
                "entry_date": p.entry_date,
                "entry_price": p.entry_price,
                "exit_date": p.exit_date,
                "exit_price": p.exit_price,
                "qty": p.qty,
                "pnl": p.pnl,
                "return_pct": p.return_pct,
            }
            for p in self.closed
        ])

    def equity_curve_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(self.equity_curve)
