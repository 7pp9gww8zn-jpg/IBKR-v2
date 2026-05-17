# IBKR-v2: Automated Swing Trading Engine

IBKR automated swing trading system using `ib_insync`, paper trading on port 4002.

## Strategy
- Trend-following momentum on daily bars
- 3% position size, 20% max total exposure
- Bracket orders with ATR-based stop/target
- Trailing stop conversion after 2×ATR profit

## Architecture
- `ibkr_quant/` — Core engine modules
- `backtest/` — Backtesting framework
- `scripts/` — CLI utilities and TUI
- `tests/` — Unit tests

## Setup
```bash
pip install -e .
cp .env.example .env
# Edit .env with your IB Gateway credentials
```