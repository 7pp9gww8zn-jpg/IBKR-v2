"""
Entrypoint for the IBKR Quant trading engine.
Usage: python scripts/run_engine.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ib_insync import util as insync_util
from ibkr_quant.engine import main

if __name__ == "__main__":
    insync_util.run(main())
