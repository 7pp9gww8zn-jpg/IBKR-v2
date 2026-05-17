"""
Main engine orchestrator: startup, scheduler, graceful shutdown.
"""
from __future__ import annotations

import asyncio
import json
import signal
import sys
from datetime import datetime
from pathlib import Path

import nest_asyncio
from apscheduler.triggers.cron import CronTrigger
import pytz

from ibkr_quant.cache import Cache
from ibkr_quant.config import Settings, load_settings
from ibkr_quant.connection import IBConnection
from ibkr_quant.logging_setup import configure, get_logger
from ibkr_quant.models import RunKind
from ibkr_quant.order_manager import place_entries
from ibkr_quant.position_manager import post_close_review, reconcile_positions
from ibkr_quant.scanner import run_scan
from ibkr_quant.scheduler import Scheduler
from ibkr_quant.universe import load_or_refresh

nest_asyncio.apply()
logger = get_logger("engine")
ET = pytz.timezone("US/Eastern")


async def _run_scan(ib_conn: IBConnection, settings: Settings, cache: Cache) -> None:
    run_id = await cache.start_run(RunKind.SCAN)
    try:
        ranked = await run_scan(ib_conn, settings, cache)
        await cache.finish_run(run_id, symbols_processed=len(ranked), signals_found=len(ranked))
        logger.info("Scan run %d complete: %d signals", run_id, len(ranked))
    except Exception as exc:
        logger.error("Scan run %d failed: %s", run_id, exc)
        await cache.finish_run(run_id)


async def _run_orders(ib_conn: IBConnection, settings: Settings, cache: Cache) -> None:
    run_id = await cache.start_run(RunKind.ORDER)
    try:
        ranked = await run_scan(ib_conn, settings, cache)
        orders = await place_entries(ib_conn, cache, settings, ranked)
        await cache.finish_run(run_id, orders_placed=len(orders))
        logger.info("Order run %d complete: %d orders", run_id, len(orders))
    except Exception as exc:
        logger.error("Order run %d failed: %s", run_id, exc)
        await cache.finish_run(run_id)


async def _run_eod_review(ib_conn: IBConnection, settings: Settings, cache: Cache) -> None:
    run_id = await cache.start_run(RunKind.EOD_REVIEW)
    try:
        await reconcile_positions(ib_conn, cache)
        await post_close_review(ib_conn, cache, settings)
        await cache.finish_run(run_id)
        logger.info("EOD review run %d complete", run_id)
    except Exception as exc:
        logger.error("EOD review run %d failed: %s", run_id, exc)
        await cache.finish_run(run_id)


async def _run_universe_refresh(ib_conn: IBConnection, settings: Settings, cache: Cache) -> None:
    from ibkr_quant.universe import refresh_universe
    run_id = await cache.start_run(RunKind.UNIVERSE_REFRESH)
    try:
        await refresh_universe(ib_conn, settings, cache)
        await cache.finish_run(run_id)
        logger.info("Universe refresh run %d complete", run_id)
    except Exception as exc:
        logger.error("Universe refresh run %d failed: %s", run_id, exc)
        await cache.finish_run(run_id)


async def _status_emitter(ib_conn: IBConnection, sched: Scheduler, cache: Cache, db_path: Path) -> None:
    status_path = db_path.parent / "engine_status.json"
    tmp_path = status_path.with_suffix(".json.tmp")
    consecutive_errors = 0
    logged_init = False

    while True:
        await asyncio.sleep(5)
        try:
            acct = ib_conn.get_account_data()
            jobs = sched.list_jobs()
            next_runs = {j["id"]: j["next_run"] for j in jobs}
            positions = ib_conn.get_positions()

            def _tag(tag: str) -> str:
                return acct.get(tag, "\u2014")

            status = {
                "timestamp": datetime.now().isoformat(),
                "connected": ib_conn.is_connected(),
                "account": {
                    "net_liq":      _tag("NetLiquidation"),
                    "cash":         _tag("TotalCashValue"),
                    "buying_power": _tag("BuyingPower"),
                    "daily_pnl":    ib_conn.get_daily_pnl(),
                },
                "positions": {
                    "count": len(positions),
                    "long": sum(1 for p in positions if p.position > 0),
                    "short": sum(1 for p in positions if p.position < 0),
                },
                "next_runs": next_runs,
            }
            tmp_path.write_text(json.dumps(status, indent=2))
            tmp_path.replace(status_path)

            if consecutive_errors > 0:
                logger.info("Status emitter recovered after %d failures", consecutive_errors)
            consecutive_errors = 0

            if not logged_init:
                logger.info("engine_status.json initialized at %s", status_path)
                logged_init = True
        except Exception as exc:
            import traceback
            consecutive_errors += 1
            if consecutive_errors == 1:
                logger.warning("Status emitter error: %s\n%s", exc, traceback.format_exc())
            else:
                logger.debug("Status emitter error [%d]: %s", consecutive_errors, exc)


async def main() -> None:
    configure()
    logger.info("=== IBKR Quant Engine starting ===")

    settings = load_settings()
    cache = Cache(settings.cache.db_path)
    await cache.connect()
    logger.info("Cache initialized at %s", settings.cache.db_path)

    ib_conn = IBConnection(
        host=settings.connection.host,
        port=settings.connection.port,
        client_id=settings.connection.client_id,
    )

    logger.info("Connecting to IB at %s:%d (mode=%s)", settings.connection.host, settings.connection.port, settings.connection.mode)
    if not await ib_conn.ensure_connected():
        logger.error("Could not connect to IB Gateway - check IB Gateway is running and API is enabled")
        sys.exit(1)

    await ib_conn.start_health_monitor()
    await ib_conn.subscribe_pnl()

    universe_rows = await load_or_refresh(ib_conn, settings, cache)
    logger.info("Universe ready: %d symbols", len(universe_rows))

    sched = Scheduler()

    scan_trigger = CronTrigger(
        day_of_week="mon-fri",
        hour=16,
        minute=30,
        timezone=ET,
    )
    order_trigger = CronTrigger(
        day_of_week="mon-fri",
        hour=9,
        minute=15,
        timezone=ET,
    )
    eod_trigger = CronTrigger(
        day_of_week="mon-fri",
        hour=16,
        minute=5,
        timezone=ET,
    )
    refresh_trigger = CronTrigger(day_of_week="sun", hour=0, minute=0, timezone=ET)

    def scan_job():
        return _run_scan(ib_conn, settings, cache)

    def order_job():
        return _run_orders(ib_conn, settings, cache)

    def eod_job():
        return _run_eod_review(ib_conn, settings, cache)

    def refresh_job():
        return _run_universe_refresh(ib_conn, settings, cache)

    sched.add_scan_job(scan_job, trigger=scan_trigger)
    sched.add_order_job(order_job, trigger=order_trigger)
    sched.add_eod_review_job(eod_job, trigger=eod_trigger)
    sched.add_weekly_universe_refresh(refresh_job, trigger=refresh_trigger)

    sched.start()
    logger.info("Scheduler started with jobs: %s", sched.list_jobs())

    status_task = asyncio.create_task(_status_emitter(ib_conn, sched, cache, settings.cache.db_path))

    stop_event = asyncio.Event()

    def signal_handler(sig, frame):
        logger.info("Received shutdown signal - initiating graceful stop")
        stop_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info("Engine running. Press Ctrl+C to stop.")
    await stop_event.wait()

    logger.info("Shutting down engine...")
    status_task.cancel()
    try:
        await status_task
    except asyncio.CancelledError:
        pass
    sched.shutdown()
    await ib_conn.disconnect()
    await cache.close()
    logger.info("Engine stopped cleanly")


if __name__ == "__main__":
    import ib_insync.util
    ib_insync.util.run(main())
