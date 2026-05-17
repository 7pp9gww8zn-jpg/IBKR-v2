"""
Universe module: load seed list, rank by IBKR 20-day ADV, persist results.
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
from ib_insync import Stock

from ibkr_quant.cache import Cache
from ibkr_quant.config import Settings
from ibkr_quant.logging_setup import get_logger
from ibkr_quant.models import UniverseRow
from ibkr_quant.universe_data import load_seed_universe

logger = get_logger("universe")


def _is_etf_or_special(contract) -> bool:
    sec = getattr(contract, "secType", "")
    if sec in ("ETF", "OPT", "FUT", "BAG", "IND"):
        return True
    return False


async def rank_by_adv(
    ib, symbols: list[str], cache: Cache, lookback_days: int = 20, delay: float = 2.0
) -> list[UniverseRow]:
    results: list[UniverseRow] = []
    total = len(symbols)
    logger.info("Ranking %d symbols by ADV via IBKR (%.1fs delay between requests)", total, delay)

    for i, sym in enumerate(symbols):
        try:
            contract = Stock(sym, "SMART", "USD")
            qualified_list = await ib.qualifyContractsAsync(contract)
            if not qualified_list:
                logger.debug("Skipping %s - could not qualify contract", sym)
                continue
            qualified = qualified_list[0]
            if _is_etf_or_special(qualified):
                logger.debug("Skipping %s - not qualified or ETF/special", sym)
                continue

            bars = await ib.reqHistoricalDataAsync(
                contract=qualified,
                endDateTime="",
                durationStr="1 M",
                barSizeSetting="1 day",
                whatToShow="TRADES",
                useRTH=True,
                formatDate=2,
            )
            await asyncio.sleep(delay)

            if len(bars) < lookback_days:
                logger.debug("Skipping %s - only %d bars (need %d)", sym, len(bars), lookback_days)
                continue

            df = pd.DataFrame(bars)
            df["date"] = pd.to_datetime(df["date"]).dt.date
            adv = df["volume"].tail(lookback_days).mean()
            last = df["close"].iloc[-1]

            if last < 1.0:
                logger.debug("Skipping %s - price %.2f below minimum", sym, last)
                continue

            results.append(
                UniverseRow(symbol=sym, adv_20=adv, last_price=last, included=True)
            )
            logger.debug("[%d/%d] %s ADV=%.0f price=%.2f", i + 1, total, sym, adv, last)

        except Exception as exc:
            logger.warning("Failed to get ADV for %s: %s", sym, exc)
            continue

    logger.info("ADV ranking complete: %d symbols qualified", len(results))
    return results


async def refresh_universe(ib, settings: Settings, cache: Cache) -> list[UniverseRow]:
    logger.info("Starting universe refresh")
    symbols = load_seed_universe()
    ranked = await rank_by_adv(
        ib,
        symbols,
        cache,
        lookback_days=settings.universe.adv_lookback_days,
        delay=settings.cache.hist_request_delay_sec,
    )
    ranked.sort(key=lambda r: r.adv_20, reverse=True)
    top = ranked[: settings.universe.universe_size]
    logger.info("Top %d symbols by ADV", len(top))

    for r in ranked[settings.universe.universe_size:]:
        r.included = False

    await cache.save_universe(ranked)
    await cache.set_metadata("universe_ranked_at", datetime.utcnow().isoformat())
    return top


def is_stale(cache: Cache, refresh_days: int) -> bool:
    import sqlite3
    db_path = cache.db_path
    if not db_path.exists():
        return True
    try:
        conn = sqlite3.connect(str(db_path))
        row = conn.execute("SELECT value FROM metadata WHERE key = 'universe_ranked_at'").fetchone()
        conn.close()
        if not row:
            return True
        last = datetime.fromisoformat(row[0])
        return (datetime.utcnow() - last).days >= refresh_days
    except Exception:
        return True


async def load_or_refresh(ib, settings: Settings, cache: Cache) -> list[UniverseRow]:
    if is_stale(cache, settings.universe.universe_refresh_days):
        logger.info("Universe stale - refreshing via IBKR ADV ranking")
        return await refresh_universe(ib, settings, cache)
    else:
        logger.info("Loading universe from cache")
        rows = await cache.load_universe(active_only=True)
        if not rows:
            logger.warning("Cache empty - refreshing universe")
            return await refresh_universe(ib, settings, cache)
        return rows
