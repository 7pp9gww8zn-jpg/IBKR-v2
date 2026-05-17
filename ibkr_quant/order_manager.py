"""
Order manager: bracket orders, pre-trade risk checks, position sizing.
"""
from __future__ import annotations

from datetime import date
from typing import Sequence

from ib_insync import BracketOrder, Order, Stock, StopOrder

from ibkr_quant.cache import Cache
from ibkr_quant.config import Settings
from ibkr_quant.connection import IBConnection
from ibkr_quant.logging_setup import get_logger
from ibkr_quant.models import OrderRecord, Position, PositionStatus, RankedSignal, Side

logger = get_logger("orders")


def _is_market_hours() -> bool:
    from datetime import datetime
    import pytz
    now_et = datetime.now(pytz.timezone("US/Eastern"))
    return 9 <= now_et.hour < 16 and now_et.weekday() < 5


async def _cancel_stale_orders(ib) -> None:
    logger.info("Cancelling stale unfilled orders from previous session")
    try:
        orders = ib.openOrders()
        for o in orders:
            ib.cancelOrder(o)
            logger.debug("Cancelled stale order: %s %s %s", o.action, o.totalQuantity, o.clientId)
    except Exception as exc:
        logger.warning("Error cancelling stale orders: %s", exc)


def _compute_position_size(
    signal: RankedSignal,
    cash: float,
    open_positions: list[Position],
    settings: Settings,
) -> float:
    max_exposure = cash * settings.risk.max_total_exposure_pct
    per_position_dollars = cash * settings.risk.per_position_pct

    current_exposure = sum(p.qty * p.entry_price for p in open_positions)
    available_exposure = max_exposure - current_exposure
    if available_exposure <= 0:
        return 0.0

    dollar_size = min(per_position_dollars, available_exposure, signal.stop_distance_atr * 50)
    qty = dollar_size / signal.entry_price
    qty = float(int(qty / 100) * 100)
    return max(100, qty)


def _validate_stop_distance(
    entry_price: float, stop_price: float, atr: float
) -> bool:
    if atr <= 0:
        return False
    stop_distance_pct = abs(entry_price - stop_price) / entry_price
    min_atr_fraction = 0.5
    max_atr_fraction = 5.0
    atr_distance = abs(entry_price - stop_price) / atr
    return min_atr_fraction <= atr_distance <= max_atr_fraction


async def place_entries(
    ib_conn: IBConnection,
    cache: Cache,
    settings: Settings,
    signals: list[RankedSignal],
) -> list[OrderRecord]:
    if _is_market_hours():
        raise RuntimeError("Must not place orders during US market hours")

    await _cancel_stale_orders(ib_conn.ib)

    logger.info("Placing orders for %d signals", len(signals))
    placed: list[OrderRecord] = []

    open_positions = await cache.get_open_positions()

    try:
        account_summary = ib_conn.ib.accountSummary()
        cash_str = next(
            (a.value for a in account_summary if a.tag == "NetLiquidation"),
            None,
        )
        cash = float(cash_str) if cash_str else 100_000.0
    except Exception:
        cash = 100_000.0

    for sig in signals:
        try:
            qty = _compute_position_size(sig, cash, open_positions, settings)
            if qty <= 0:
                logger.debug("%s: no position size available", sig.symbol)
                continue

            atr = sig.atr if sig.atr > 0 else 1.0
            stop_price = (
                sig.entry_price - settings.risk.atr_stop_multiple * atr
                if sig.direction.value == "long"
                else sig.entry_price + settings.risk.atr_stop_multiple * atr
            )
            target_price = (
                sig.entry_price + settings.risk.atr_target_multiple * atr
                if sig.direction.value == "long"
                else sig.entry_price - settings.risk.atr_target_multiple * atr
            )

            if not _validate_stop_distance(sig.entry_price, stop_price, atr):
                logger.warning(
                    "%s: stop distance %.2f from entry %.2f is outside %.1f-%.1f ATR range - skipping",
                    sig.symbol, abs(sig.entry_price - stop_price), sig.entry_price, 0.5, 5.0
                )
                continue

            action = "BUY" if sig.direction.value == "long" else "SELL"
            contract = Stock(sig.symbol, "SMART", "USD")

            parent = StopOrder(
                action=action,
                totalQuantity=qty,
                stopPrice=sig.entry_price,
                tif="DAY",
                orderId=0,
            )

            bracket = BracketOrder(
                parent=parent,
                takeProfitPrice=target_price,
                stopLossPrice=stop_price,
            )

            for leg in bracket:
                ib_conn.ib.placeOrder(contract, leg)
                rec = OrderRecord(
                    symbol=sig.symbol,
                    side=Side(sig.direction.value),
                    order_type=leg.orderType,
                    qty=qty,
                    price=leg.stopPrice or leg.lmtPrice or 0,
                    status="working",
                )
                order_id = await cache.record_order(rec)
                rec.order_id = order_id
                placed.append(rec)
                logger.info(
                    "Placed %s %s %.0f @ stop=%.2f tp=%.2f sl=%.2f",
                    sig.setup_name, sig.symbol, qty, sig.entry_price, target_price, stop_price
                )

        except Exception as exc:
            logger.error("Failed to place order for %s: %s", sig.symbol, exc)
            continue

    logger.info("Order placement complete: %d orders placed", len(placed))
    return placed
