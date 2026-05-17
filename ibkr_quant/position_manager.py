"""
Position manager: trailing stops, exit signals, EOD review.
"""
from __future__ import annotations

from datetime import date, timedelta

from ibkr_quant.cache import Cache
from ibkr_quant.config import Settings
from ibkr_quant.connection import IBConnection
from ibkr_quant.logging_setup import get_logger
from ibkr_quant.models import Position, PositionStatus, Side

logger = get_logger("position")


def _is_market_hours() -> bool:
    from datetime import datetime
    import pytz
    now_et = datetime.now(pytz.timezone("US/Eastern"))
    return 9 <= now_et.hour < 16 and now_et.weekday() < 5


async def post_close_review(
    ib_conn: IBConnection,
    cache: Cache,
    settings: Settings,
) -> None:
    if _is_market_hours():
        raise RuntimeError("Must not run position review during US market hours")

    logger.info("=== Starting post-close position review ===")
    open_positions = await cache.get_open_positions()
    if not open_positions:
        logger.info("No open positions to review")
        return

    try:
        ib_positions = {
            pos.contract.symbol: pos
            for pos in ib_conn.ib.positions()
        }
    except Exception as exc:
        logger.warning("Could not fetch IB positions: %s", exc)
        ib_positions = {}

    updated = 0
    for pos in open_positions:
        ib_pos = ib_positions.get(pos.symbol)
        if ib_pos is None:
            logger.debug("Position %s not in IB - may have been closed", pos.symbol)
            continue

        try:
            bars = await ib_conn.ib.reqHistoricalDataAsync(
                contract=ib_pos.contract,
                endDateTime="",
                durationStr="2 D",
                barSizeSetting="1 day",
                whatToShow="TRADES",
                useRTH=True,
                formatDate=2,
            )
        except Exception as exc:
            logger.warning("Could not fetch latest bar for %s: %s", pos.symbol, exc)
            continue

        if not bars:
            continue

        from ibkr_quant.indicators import atr as _atr
        import pandas as pd
        high = max(b.high for b in bars)
        low = min(b.low for b in bars)
        close = bars[-1].close

        if pos.side == Side.LONG:
            pos.highest_high = max(pos.highest_high, high)
            trail_atr = settings.risk.trailing_atr_multiple * pos.stop_price / (pos.entry_price / pos.stop_price)
            new_trailing = pos.highest_high - trail_atr
            if pos.trailing_stop_price is None or new_trailing > pos.trailing_stop_price:
                pos.trailing_stop_price = new_trailing
                logger.info(
                    "%s: trailing stop updated to %.2f (highest=%.2f)",
                    pos.symbol, new_trailing, pos.highest_high
                )
        else:
            pos.lowest_low = min(pos.lowest_low, low)
            trail_atr = settings.risk.trailing_atr_multiple * pos.stop_price / (pos.entry_price / pos.stop_price)
            new_trailing = pos.lowest_low + trail_atr
            if pos.trailing_stop_price is None or new_trailing < pos.trailing_stop_price:
                pos.trailing_stop_price = new_trailing

        pos.holding_days += 1

        if pos.holding_days >= settings.risk.max_holding_days:
            logger.info("%s: max holding days reached (%d) - marking for timeout exit", pos.symbol, pos.holding_days)
            pos.status = PositionStatus.TIMEOUT

        await cache.update_position(pos)
        updated += 1

    logger.info("Position review complete: %d positions updated", updated)


async def reconcile_positions(
    ib_conn: IBConnection,
    cache: Cache,
) -> None:
    try:
        ib_pos_list = ib_conn.ib.positions()
    except Exception as exc:
        logger.warning("Could not fetch IB positions for reconciliation: %s", exc)
        return

    ib_symbols = {p.contract.symbol for p in ib_pos_list}
    cached_positions = await cache.get_all_positions()

    for pos in cached_positions:
        if pos.status != PositionStatus.OPEN:
            continue
        if pos.symbol not in ib_symbols:
            pos.status = PositionStatus.CLOSED
            await cache.update_position(pos)
            logger.info("Position %s closed (not in IB positions)", pos.symbol)
