"""
APScheduler-based scheduler for post-close scan, pre-open order placement, EOD review.
All times in US/Eastern. Engine is in SGT but jobs run on IBKR schedule.
"""
from __future__ import annotations

import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from ibkr_quant.logging_setup import get_logger

logger = get_logger("scheduler")

ET = pytz.timezone("US/Eastern")


def _scan_time() -> CronTrigger:
    parts = "16,30".split(",")
    return CronTrigger(
        day_of_week="mon-fri",
        hour=int(parts[0]),
        minute=int(parts[1]),
        timezone=ET,
    )


def _order_time() -> CronTrigger:
    parts = "09,15".split(",")
    return CronTrigger(
        day_of_week="mon-fri",
        hour=int(parts[0]),
        minute=int(parts[1]),
        timezone=ET,
    )


def _eod_review_time() -> CronTrigger:
    parts = "16,05".split(",")
    return CronTrigger(
        day_of_week="mon-fri",
        hour=int(parts[0]),
        minute=int(parts[1]),
        timezone=ET,
    )


def _sunday_midnight() -> CronTrigger:
    return CronTrigger(day_of_week="sun", hour=0, minute=0, timezone=ET)


class Scheduler:
    def __init__(self) -> None:
        self._scheduler = AsyncIOScheduler(timezone=str(ET))
        self._jobs: dict[str, object] = {}

    def add_scan_job(self, func, trigger: CronTrigger | None = None, **kwargs) -> None:
        if trigger is None:
            trigger = _scan_time()
        self._scheduler.add_job(func, trigger, id="scan", **kwargs)
        logger.info("Scheduled scan job at %s ET", trigger)

    def add_order_job(self, func, trigger: CronTrigger | None = None, **kwargs) -> None:
        if trigger is None:
            trigger = _order_time()
        self._scheduler.add_job(func, trigger, id="orders", **kwargs)
        logger.info("Scheduled order job at %s ET", trigger)

    def add_eod_review_job(self, func, trigger: CronTrigger | None = None, **kwargs) -> None:
        if trigger is None:
            trigger = _eod_review_time()
        self._scheduler.add_job(func, trigger, id="eod_review", **kwargs)
        logger.info("Scheduled EOD review job at %s ET", trigger)

    def add_weekly_universe_refresh(self, func, trigger: CronTrigger | None = None, **kwargs) -> None:
        if trigger is None:
            trigger = _sunday_midnight()
        self._scheduler.add_job(func, trigger, id="universe_refresh", **kwargs)
        logger.info("Scheduled weekly universe refresh")

    def start(self) -> None:
        self._scheduler.start()
        logger.info("Scheduler started")

    def shutdown(self, wait: bool = True) -> None:
        self._scheduler.shutdown(wait=wait)
        logger.info("Scheduler stopped")

    def run_now(self, job_id: str) -> None:
        job = self._scheduler.get_job(job_id)
        if job:
            job.modify(next_run_time=None)
            logger.info("Triggered manual run for job '%s'", job_id)
        else:
            logger.warning("No job found with id '%s'", job_id)

    def list_jobs(self) -> list[dict]:
        return [
            {"id": j.id, "next_run": str(j.next_run_time) if j.next_run_time else None}
            for j in self._scheduler.get_jobs()
        ]
