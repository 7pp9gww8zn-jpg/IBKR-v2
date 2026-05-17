"""
Post-close scanner: fetch latest bar, compute indicators, detect setups, rank signals.
"""
from __future__ import annotations

import asyncio
from datetime import date, timedelta

import pandas as pd
from ib_insync import Stock

from ibkr_quant.cache import Cache
from ibkr_quant.config import Settings
from ibkr_quant.connection import IBConnection
from ibkr_quant.indicators import add_indicators
from ibkr_quant.logging_setup import get_logger
from ibkr_quant.models import RankedSignal, RunKind, Side, SignalCore
from ibkr_quant.strategy import build_setups, run_setups

logger = get_logger("scanner")


def _enforce_market_hours() -> None:
    from datetime import datetime
    import pytz
    now_et = datetime.now(pytz.timezone("US/Eastern"))
    if 9 <= now_et.hour < 16 and now_et.weekday() < 5:
        raise RuntimeError("Scanner must not run during US market hours (9:30am-4:00pm ET)")


async def _fetch_latest_bar(
    ib, symbol: str, cache: Cache, delay: float
) -> pd.DataFrame | None:
    try:
        contract = Stock(symbol, "SMART", "USD")
        qualified = ib.qualifyContract(contract)
        if not qualified:
            return None

        bars = await ib.reqHistoricalDataAsync(
            contract=qualified,
            endDateTime="",
            durationStr="2 D",
            barSizeSetting="1 day",
            whatToShow="TRADES",
            useRTH=True,
            formatDate=2,
        )
        await asyncio.sleep(delay)

        if not bars:
            return None

        df = pd.DataFrame(bars)
        df.columns = ["date", "open", "high", "low", "close", "volume"]
        df["date"] = pd.to_datetime(df["date"]).dt.date
        df["symbol"] = symbol
        await cache.upsert_bars(symbol, df)

        return df

    except Exception as exc:
        logger.debug("Could not fetch latest bar for %s: %s", symbol, exc)
        return None


def _compute_entry_prices(df: pd.DataFrame, direction: Side) -> tuple[float, float]:
    yesterday = df.iloc[-1] if len(df) >= 1 else None
    if yesterday is None:
        return 0.0, 0.0
    if direction == Side.LONG:
        entry = float(yesterday["high"])
    else:
        entry = float(yesterday["low"])
    return entry, float(yesterday["close"])


async def run_scan(
    ib_conn: IBConnection,
    settings: Settings,
    cache: Cache,
) -> list[RankedSignal]:
    _enforce_market_hours()
    logger.info("=== Starting post-close scan ===")

    universe = await cache.load_universe(active_only=True)
    if not universe:
        logger.warning("Universe is empty - cannot run scan")
        return []

    symbols = [r.symbol for r in universe]
    logger.info("Scanning %d symbols", len(symbols))

    signals: list[SignalCore] = []
    delay = settings.cache.hist_request_delay_sec
    ind = settings.indicators
    strat = settings.strategy
    setups = build_setups(ind, strat)

    processed = 0
    for sym in symbols:
        df_new = await _fetch_latest_bar(ib_conn.ib, sym, cache, delay)
        if df_new is None or df_new.empty:
            continue

        df_hist = await cache.get_bars(sym, lookback_days=365 * 3)
        if df_hist.empty or len(df_hist) < 200:
            continue

        df_combined = pd.concat([df_hist, df_new], ignore_index=True)
        df_combined = df_combined.drop_duplicates(subset=["date"], keep="last")
        df_combined = df_combined.sort_values("date").reset_index(drop=True)
        df_combined["symbol"] = sym

        sigs = run_setups(df_combined, setups, ind)

        for sig in sigs:
            entry_price, last_close = _compute_entry_prices(df_combined, Side(sig.direction.value))
            sig.entry_price = entry_price
            atr = sig.atr if sig.atr > 0 else 1.0
            sig.stop_distance_atr = atr
            signals.append(sig)

        processed += 1
        if processed % 50 == 0:
            logger.info("Scan progress: %d/%d symbols, %d signals so far", processed, len(symbols), len(signals))

    if not signals:
        logger.info("No signals found in scan")
        return []

    signals.sort(key=lambda s: s.score, reverse=True)
    ranked: list[RankedSignal] = []
    for i, sig in enumerate(signals):
        r = RankedSignal(**sig.model_dump(), rank=i + 1)
        ranked.append(r)

    logger.info(
        "Scan complete: %d signals found from %d symbols processed",
        len(ranked),
        processed,
    )
    return ranked
