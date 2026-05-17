"""
SQLite cache for daily bars, universe, positions, and run history.
"""
from __future__ import annotations

import aiosqlite
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from ibkr_quant.models import (
    OrderRecord,
    Position,
    PositionStatus,
    RunKind,
    Side,
    UniverseRow,
)
from ibkr_quant.logging_setup import get_logger

logger = get_logger("cache")

SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_bars (
    symbol TEXT NOT NULL,
    bar_date DATE NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL NOT NULL,
    PRIMARY KEY (symbol, bar_date)
);

CREATE TABLE IF NOT EXISTS universe (
    symbol TEXT PRIMARY KEY,
    adv_20 REAL,
    last_price REAL,
    ranked_at TIMESTAMP,
    included INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS positions (
    symbol TEXT PRIMARY KEY,
    side TEXT NOT NULL,
    qty REAL NOT NULL,
    entry_price REAL NOT NULL,
    entry_date DATE NOT NULL,
    limit_price REAL,
    stop_price REAL NOT NULL,
    target_price REAL NOT NULL,
    highest_high REAL NOT NULL,
    lowest_low REAL NOT NULL,
    status TEXT NOT NULL,
    trailing_stop_price REAL,
    holding_days INTEGER DEFAULT 0,
    unrealized_pnl REAL
);

CREATE TABLE IF NOT EXISTS orders (
    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    order_type TEXT NOT NULL,
    status TEXT NOT NULL,
    qty REAL NOT NULL DEFAULT 0,
    price REAL NOT NULL DEFAULT 0,
    filled_price REAL,
    placed_at TIMESTAMP,
    filled_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    started_at TIMESTAMP NOT NULL,
    finished_at TIMESTAMP,
    summary TEXT,
    symbols_processed INTEGER DEFAULT 0,
    signals_found INTEGER DEFAULT 0,
    orders_placed INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


class Cache:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(str(self.db_path))
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(SCHEMA)
        await self._conn.commit()
        logger.info("Cache connected: %s", self.db_path)

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            await self.connect()
        assert self._conn is not None
        return self._conn

    async def upsert_bars(self, symbol: str, df: pd.DataFrame) -> None:
        c = await self.conn()
        rows = [
            (
                symbol,
                r["date"],
                r["open"],
                r["high"],
                r["low"],
                r["close"],
                r["volume"],
            )
            for r in df.to_dict("records")
        ]
        await c.executemany(
            """
            INSERT OR REPLACE INTO daily_bars (symbol, bar_date, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        await c.commit()

    async def get_bars(
        self, symbol: str, lookback_days: int | None = None, end_date: date | None = None
    ) -> pd.DataFrame:
        c = await self.conn()
        query = "SELECT * FROM daily_bars WHERE symbol = ?"
        args: list[Any] = [symbol]
        if end_date:
            query += " AND bar_date <= ?"
            args.append(end_date.isoformat())
        if lookback_days:
            query += " ORDER BY bar_date DESC LIMIT ?"
            args.append(lookback_days)
        else:
            query += " ORDER BY bar_date ASC"
        rows = await c.execute(query, args)
        records = await rows.fetchall()
        if not records:
            return pd.DataFrame()
        df = pd.DataFrame.from_records(
            records, columns=["symbol", "date", "open", "high", "low", "close", "volume"]
        )
        df["date"] = pd.to_datetime(df["date"])
        return df

    async def latest_bar_date(self, symbol: str) -> date | None:
        c = await self.conn()
        row = await c.execute(
            "SELECT MAX(bar_date) FROM daily_bars WHERE symbol = ?", (symbol,)
        )
        val = await row.fetchone()
        if val and val[0]:
            return date.fromisoformat(val[0])
        return None

    async def save_universe(self, rows: list[UniverseRow]) -> None:
        c = await self.conn()
        now = datetime.utcnow().isoformat()
        for r in rows:
            await c.execute(
                """
                INSERT OR REPLACE INTO universe (symbol, adv_20, last_price, ranked_at, included)
                VALUES (?, ?, ?, ?, ?)
                """,
                (r.symbol, r.adv_20, r.last_price, now, int(r.included)),
            )
        await c.commit()

    async def load_universe(self, active_only: bool = True) -> list[UniverseRow]:
        c = await self.conn()
        query = "SELECT * FROM universe"
        if active_only:
            query += " WHERE included = 1"
        query += " ORDER BY adv_20 DESC"
        rows = await c.execute(query)
        records = await rows.fetchall()
        return [
            UniverseRow(
                symbol=r["symbol"],
                adv_20=r["adv_20"] or 0.0,
                last_price=r["last_price"] or 0.0,
                included=bool(r["included"]),
            )
            for r in records
        ]

    async def record_position(self, pos: Position) -> None:
        c = await self.conn()
        await c.execute(
            """
            INSERT OR REPLACE INTO positions
            (symbol, side, qty, entry_price, entry_date, stop_price, target_price,
             highest_high, lowest_low, status, trailing_stop_price, holding_days)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                pos.symbol,
                pos.side.value,
                pos.qty,
                pos.entry_price,
                pos.entry_date.isoformat(),
                pos.stop_price,
                pos.target_price,
                pos.highest_high,
                pos.lowest_low,
                pos.status.value,
                pos.trailing_stop_price,
                pos.holding_days,
            ),
        )
        await c.commit()

    async def update_position(self, pos: Position) -> None:
        await self.record_position(pos)

    async def get_open_positions(self) -> list[Position]:
        c = await self.conn()
        rows = await c.execute(
            "SELECT * FROM positions WHERE status = ?", (PositionStatus.OPEN.value,)
        )
        records = await rows.fetchall()
        return [self._row_to_position(r) for r in records]

    async def get_all_positions(self) -> list[Position]:
        c = await self.conn()
        rows = await c.execute("SELECT * FROM positions")
        records = await rows.fetchall()
        return [self._row_to_position(r) for r in records]

    def _row_to_position(self, r: aiosqlite.Row) -> Position:
        return Position(
            symbol=r["symbol"],
            side=Side(r["side"]),
            qty=r["qty"],
            entry_price=r["entry_price"],
            entry_date=date.fromisoformat(r["entry_date"]),
            stop_price=r["stop_price"],
            target_price=r["target_price"],
            highest_high=r["highest_high"],
            lowest_low=r["lowest_low"],
            status=PositionStatus(r["status"]),
            trailing_stop_price=r["trailing_stop_price"],
            holding_days=r["holding_days"],
        )

    async def record_order(self, order: OrderRecord) -> int:
        c = await self.conn()
        cursor = await c.execute(
            """
            INSERT INTO orders (symbol, side, order_type, status, qty, price, filled_price, placed_at, filled_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order.symbol,
                order.side.value,
                order.order_type,
                order.status.value,
                order.qty,
                order.price,
                order.filled_price,
                order.placed_at.isoformat() if order.placed_at else None,
                order.filled_at.isoformat() if order.filled_at else None,
            ),
        )
        await c.commit()
        return cursor.lastrowid or 0

    async def update_order_status(
        self, order_id: int, status: str, filled_price: float | None = None
    ) -> None:
        c = await self.conn()
        await c.execute(
            "UPDATE orders SET status = ?, filled_price = ? WHERE order_id = ?",
            (status, filled_price, order_id),
        )
        await c.commit()

    async def start_run(self, kind: RunKind) -> int:
        c = await self.conn()
        cursor = await c.execute(
            "INSERT INTO runs (kind, started_at) VALUES (?, ?)",
            (kind.value, datetime.utcnow().isoformat()),
        )
        await c.commit()
        return cursor.lastrowid or 0

    async def finish_run(
        self,
        run_id: int,
        symbols_processed: int = 0,
        signals_found: int = 0,
        orders_placed: int = 0,
        summary: dict | None = None,
    ) -> None:
        c = await self.conn()
        import json

        await c.execute(
            """
            UPDATE runs SET finished_at = ?, symbols_processed = ?, signals_found = ?,
            orders_placed = ?, summary = ?
            WHERE run_id = ?
            """,
            (
                datetime.utcnow().isoformat(),
                symbols_processed,
                signals_found,
                orders_placed,
                json.dumps(summary) if summary else None,
                run_id,
            ),
        )
        await c.commit()

    async def get_metadata(self, key: str) -> str | None:
        c = await self.conn()
        row = await c.execute("SELECT value FROM metadata WHERE key = ?", (key,))
        r = await row.fetchone()
        return r["value"] if r else None

    async def set_metadata(self, key: str, value: str) -> None:
        c = await self.conn()
        await c.execute(
            "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
            (key, value),
        )
        await c.commit()
