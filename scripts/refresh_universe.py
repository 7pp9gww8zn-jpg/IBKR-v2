"""
Refresh universe: rank top-500 by IBKR ADV and save to cache.
Run weekly or on demand.
Usage: python scripts/refresh_universe.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ib_insync import util as insync_util
from ibkr_quant.cache import Cache
from ibkr_quant.config import load_settings
from ibkr_quant.connection import IBConnection
from ibkr_quant.logging_setup import configure
from ibkr_quant.universe import refresh_universe


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

    await refresh_universe(ib_conn.ib, settings, cache)
    await ib_conn.disconnect()
    await cache.close()
    print("Universe refresh complete")


if __name__ == "__main__":
    insync_util.run(main())
