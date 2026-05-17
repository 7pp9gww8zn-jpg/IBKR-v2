"""
Pydantic models for all structured data in the system.
"""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Side(str, Enum):
    LONG = "long"
    SHORT = "short"


class OrderStatus(str, Enum):
    PENDING = "pending"
    WORKING = "working"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class PositionStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    STOPPED_OUT = "stopped_out"
    TARGETHit = "target_hit"
    TIMEOUT = "timeout"


class Regime(str, Enum):
    UPTREND = "uptrend"
    DOWNTREND = "downtrend"
    REVERSAL_BULL = "reversal_bull"
    REVERSAL_BEAR = "reversal_bear"
    CONSOLIDATION = "consolidation"
    UNKNOWN = "unknown"


class SignalDirection(str, Enum):
    LONG = "long"
    SHORT = "short"


class RunKind(str, Enum):
    SCAN = "scan"
    ORDER = "order"
    EOD_REVIEW = "eod_review"
    UNIVERSE_REFRESH = "universe_refresh"


class Bar(BaseModel):
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: float


class UniverseRow(BaseModel):
    symbol: str
    adv_20: float
    last_price: float
    included: bool = True


class SignalCore(BaseModel):
    symbol: str
    direction: SignalDirection
    regime: Regime
    setup_name: str
    entry_price: float
    stop_distance_atr: float
    rsi: float
    macd_hist: float
    atr: float
    relative_volume: float
    score: float = 0.0


class RankedSignal(SignalCore):
    rank: int = 0
    size_dollars: float = 0.0


class Position(BaseModel):
    symbol: str
    side: Side
    qty: float
    entry_price: float
    entry_date: date
    stop_price: float
    target_price: float
    highest_high: float
    lowest_low: float
    status: PositionStatus = PositionStatus.OPEN
    trailing_stop_price: float | None = None
    holding_days: int = 0


class OrderRecord(BaseModel):
    order_id: int | None = None
    symbol: str
    side: Side
    order_type: str
    status: OrderStatus = OrderStatus.PENDING
    qty: float = 0.0
    price: float = 0.0
    filled_price: float | None = None
    placed_at: datetime | None = None
    filled_at: datetime | None = None


class RunRecord(BaseModel):
    run_id: int | None = None
    kind: RunKind
    started_at: datetime
    finished_at: datetime | None = None
    summary: dict | None = None
    symbols_processed: int = 0
    signals_found: int = 0
    orders_placed: int = 0
