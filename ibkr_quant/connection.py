"""
IB Gateway connection lifecycle with health monitoring and reconnection.
"""
from __future__ import annotations

import asyncio
from typing import Callable

from ib_insync import IB, util

from ibkr_quant.logging_setup import get_logger

logger = get_logger("connection")

INFO_CODES = {2104, 2106, 2107, 2108, 2158}
WARN_CODES = {2103, 2105, 2157, 2110}
CONNECT_CODES = {1100, 1102, 504}
PACING_CODE = 162


class IBConnection:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 4002,
        client_id: int = 17,
    ) -> None:
        self.host = host
        self.port = port
        self.client_id = client_id
        self._ib = IB()
        self._health_task: asyncio.Task[None] | None = None
        self._stopping = False
        self._connection_callbacks: list[Callable[[bool], None]] = []
        self._pnl = None

    @property
    def ib(self) -> IB:
        return self._ib

    def is_connected(self) -> bool:
        return self._ib.isConnected()

    def on_connection_change(self, cb: Callable[[bool], None]) -> None:
        self._connection_callbacks.append(cb)

    def _notify_connection(self, connected: bool) -> None:
        for cb in self._connection_callbacks:
            try:
                cb(connected)
            except Exception:
                pass

    def _register_error_handler(self) -> None:
        def on_error(reqId: int, errorCode: int, errorString: str, contract: object = None) -> None:
            if errorCode in INFO_CODES:
                logger.debug("IB info [%d]: %s", errorCode, errorString)
            elif errorCode in WARN_CODES or errorCode == PACING_CODE:
                logger.warning("IB warning [%d]: %s", errorCode, errorString)
            elif errorCode == 1100 or errorCode == 504:
                logger.error("IB connection lost [%d]: %s", errorCode, errorString)
                self._notify_connection(False)
            elif errorCode == 1102:
                logger.info("IB connection restored: %s", errorString)
                self._notify_connection(True)
            else:
                logger.error("IB error %d (reqId=%d): %s", errorCode, reqId, errorString)

        self._ib.errorEvent += on_error

    async def connect(self, timeout: int = 30) -> bool:
        logger.info("Connecting to IB Gateway at %s:%d (client_id=%d)", self.host, self.port, self.client_id)
        self._register_error_handler()
        try:
            await self._ib.connectAsync(
                host=self.host,
                port=self.port,
                clientId=self.client_id,
                timeout=timeout,
            )
            logger.info("Connected to IB successfully")
            self._notify_connection(True)
            return True
        except Exception as exc:
            logger.error("Failed to connect to IB: %s", exc)
            return False

    async def ensure_connected(self, max_retries: int = 10) -> bool:
        if self._ib.isConnected():
            return True
        retry_delay = 5.0
        for attempt in range(1, max_retries + 1):
            logger.info("Connection attempt %d/%d", attempt, max_retries)
            connected = await self.connect()
            if connected:
                return True
            if attempt < max_retries:
                logger.warning("Retrying in %.0fs...", retry_delay)
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 1.5, 60.0)
        logger.error("Could not restore IB connection after %d attempts", max_retries)
        return False

    async def disconnect(self) -> None:
        self._stopping = True
        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass
        if self._ib.isConnected():
            self._ib.disconnect()
            logger.info("Disconnected from IB")
        self._notify_connection(False)

    async def start_health_monitor(self, interval: int = 60) -> None:
        async def _health_loop() -> None:
            while not self._stopping:
                await asyncio.sleep(interval)
                try:
                    await self._ib.reqCurrentTimeAsync()
                    logger.debug("Health check OK")
                except Exception as exc:
                    logger.warning("Health check failed: %s", exc)
                    if not self._stopping:
                        await self.ensure_connected()

        self._health_task = asyncio.create_task(_health_loop())

    def qualify_contract(self, contract):
        return self._ib.qualifyContract(contract)

    def get_account_data(self) -> dict:
        if not self._ib.isConnected():
            return {}
        try:
            values = self._ib.accountSummary()
            out = {}
            for v in values:
                out[v.tag] = v.value
            return out
        except Exception:
            return {}

    def get_positions(self) -> list:
        if not self._ib.isConnected():
            return []
        try:
            return self._ib.positions()
        except Exception:
            return []

    def get_open_orders(self) -> list:
        if not self._ib.isConnected():
            return []
        try:
            return self._ib.openOrders()
        except Exception:
            return []

    async def subscribe_pnl(self) -> None:
        try:
            accounts = self._ib.managedAccounts()
            if accounts:
                self._pnl = self._ib.reqPnL(accounts[0])
                logger.info("Subscribed to PnL for account %s", accounts[0])
            else:
                logger.warning("No managed accounts found for PnL subscription")
        except Exception as exc:
            logger.warning("Could not subscribe to PnL: %s", exc)
            self._pnl = None

    def get_daily_pnl(self) -> float | None:
        if self._pnl is None:
            return None
        try:
            val = self._pnl.dailyPnL
            if val != val:
                return None
            return val
        except Exception:
            return None


__all__ = ["IBConnection"]
