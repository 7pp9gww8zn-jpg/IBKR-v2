"""
Backfill historical daily bars for the universe.
One-shot script - run once before the first engine start.
Usage: python scripts/backfill_history.py
"""
from __future__ import annotations

import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ib_insync import util as insync_util
from ibkr_quant.cache import Cache
from ibkr_quant.config import load_settings
from ibkr_quant.connection import IBConnection
from ibkr_quant.logging_setup import configure, get_logger
from ibkr_quant.universe import load_seed_universe

logger = get_logger("backfill")


def _contract(ib, sym: str):
    from ib_insync import Stock
    c = Stock(sym, "SMART", "USD")
    qualified = ib.qualifyContract(c)
    return qualified


async def backfill_symbol(
    ib, sym: str, cache: Cache, duration: str, delay: float
) -> int:
    try:
        contract = _contract(ib, sym)
        if not contract:
            return 0

        bars = await ib.reqHistoricalDataAsync(
            contract=contract,
            endDateTime="",
            durationStr=duration,
            barSizeSetting="1 day",
            whatToShow="TRADES",
            useRTH=True,
            formatDate=2,
        )
        await asyncio.sleep(delay)

        if not bars:
            return 0

        import pandas as pd
        df = pd.DataFrame(bars)
        df.columns = ["date", "open", "high", "low", "close", "volume"]
        df["date"] = pd.to_datetime(df["date"]).dt.date
        await cache.upsert_bars(sym, df)
        logger.debug("Backfilled %s: %d bars", sym, len(df))
        return len(df)

    except Exception as exc:
        logger.warning("Backfill failed for %s: %s", sym, exc)
        return 0


async def main() -> None:
    configure()
    settings = load_settings()
    cache = Cache(settings.cache.db_path)
    await cache.connect()

    ib_conn = IBConnection(
        host=settings.connection.host,
        port=settings.connection.port,
        client_id=settings.connection.client_id,
    )
    if not await ib_conn.connect():
        print("FATAL: Could not connect to IB Gateway")
        sys.exit(1)

    symbols = load_seed_universe()
    duration = f"{settings.cache.history_years} Y"
    delay = settings.cache.hist_request_delay_sec

    logger.info("Backfilling %d symbols with duration=%s", len(symbols), duration)
    total_bars = 0
    for i, sym in enumerate(symbols):
        n = await backfill_symbol(ib_conn.ib, sym, cache, duration, delay)
        total_bars += n
        if (i + 1) % 50 == 0:
            logger.info("Progress: %d/%d symbols (%d total bars)", i + 1, len(symbols), total_bars)

    logger.info("Backfill complete: %d symbols, %d total bars", len(symbols), total_bars)
    await ib_conn.disconnect()
    await cache.close()


if __name__ == "__main__":
    insync_util.run(main())
