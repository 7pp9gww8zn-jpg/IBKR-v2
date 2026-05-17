"""
IBKR Quant live dashboard TUI.

Reads from SQLite + engine_status.json + log file - runs independently from the engine.
Refresh every 5 seconds. Keyboard shortcuts: q=quit r=refresh p=pause /=filter Esc=clear

Usage:
    python scripts/tui.py
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent.parent))

from rich import box
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.table import Table
from rich.text import Text

from ibkr_quant.config import load_settings

ET = ZoneInfo("America/New_York")
ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / "data" / "ibkr.db"
LOG_PATH = ROOT / "logs" / "trading.log"
STATUS_PATH = ROOT / "data" / "engine_status.json"
REFRESH_SECS = 5
LOG_LINES = 20


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _fetch(query: str, params: tuple = ()) -> list[sqlite3.Row]:
    try:
        conn = _db()
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return rows
    except Exception:
        return []


def universe_count() -> int:
    try:
        conn = _db()
        r = conn.execute("SELECT COUNT(*) FROM universe WHERE included=1").fetchone()
        conn.close()
        return r[0] if r else 0
    except Exception:
        return 0


def open_positions() -> list[sqlite3.Row]:
    return _fetch("SELECT * FROM positions WHERE status='open' ORDER BY entry_date")


def recent_orders(n: int = 8) -> list[sqlite3.Row]:
    return _fetch("SELECT * FROM orders ORDER BY order_id DESC LIMIT ?", (n,))


def recent_runs(n: int = 6) -> list[sqlite3.Row]:
    return _fetch("SELECT * FROM runs ORDER BY run_id DESC LIMIT ?", (n,))


def tail_log(n: int = LOG_LINES, filter_re: str | None = None) -> list[str]:
    try:
        with open(LOG_PATH, encoding="utf-8", errors="replace") as f:
            lines = [l.rstrip() for l in f]
        if filter_re:
            pat = re.compile(filter_re, re.IGNORECASE)
            lines = [l for l in lines if pat.search(l)]
        return [l for l in deque(lines, maxlen=max(n, 100))]
    except Exception:
        return ["(log file not found)"]


def load_engine_status() -> tuple[dict, float | None]:
    try:
        if STATUS_PATH.exists():
            mtime = STATUS_PATH.stat().st_mtime
            age = time.time() - mtime
            return json.loads(STATUS_PATH.read_text()), age
    except Exception:
        pass
    return {}, None


def _next_weekday_et(hour: int, minute: int) -> str:
    now = datetime.now(ET)
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    for _ in range(10):
        if candidate > now and candidate.weekday() < 5:
            break
        candidate += timedelta(days=1)
    delta = candidate - now
    if delta.total_seconds() < 3600:
        return f"{candidate:%a %H:%M ET} (~{int(delta.total_seconds()//60)}m)"
    if delta.days == 0:
        return f"{candidate:%a %H:%M ET} (~{int(delta.total_seconds()//3600)}h)"
    return f"{candidate:%a %d %b %H:%M ET}"


def _parse_next_run(raw: str | None) -> str:
    if not raw or raw == "None":
        return "[dim]-[\/dim]"
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        dt_et = dt.astimezone(ET)
        return dt_et.strftime("%a %H:%M ET")
    except Exception:
        return raw or "-"


def _pct_color(val: float) -> str:
    if val > 0:
        pct = val * 100
        if pct >= 5:
            return "bold green"
        if pct >= 1:
            return "green"
        return "dim green"
    if val < 0:
        pct = val * 100
        if pct <= -5:
            return "bold red"
        if pct <= -1:
            return "red"
        return "dim red"
    return "white"


def heartbeat_markup() -> Text:
    try:
        elapsed = time.time() - LOG_PATH.stat().st_mtime
        if elapsed < 15:
            return Text("● LIVE", style="bold green")
        if elapsed < 120:
            return Text(f"● {int(elapsed)}s ago", style="yellow")
        return Text(f"● stale {int(elapsed // 60)}m", style="red")
    except Exception:
        return Text("● NO LOG", style="red")


def connection_badge(connected: bool) -> Text:
    if connected:
        return Text(" CONNECTED ", style="bold green on #1a3a1a")
    return Text(" DISCONNECTED ", style="bold red on #3a1a1a")


# ── panel builders ────────────────────────────────────────────────────────────
def header_panel(status: dict, univ: int, mode: str, paused: bool, status_age: float | None) -> Panel:
    now_et = datetime.now(ET)
    now_utc = datetime.now(timezone.utc)
    conn = status.get("connected", False)
    acct = status.get("account", {})

    if status_age is None:
        banner_text = "WAITING FOR ENGINE - run 'python scripts/run_engine.py' to start"
        t = Text()
        t.append(f" {banner_text} ", style="bold white on red")
        return Panel(t, style="red", padding=0)

    if status_age > 120:
        age_s = int(status_age)
        banner_text = f"ENGINE OFFLINE - last snapshot {age_s}s ago"
        t = Text()
        t.append(f" {banner_text} ", style="bold white on red")
        return Panel(t, style="red", padding=0)

    t = Text()
    t.append(" IBKR QUANT  ", style="bold cyan on #0a1a2a")
    mode_style = "bold yellow" if mode == "paper" else "bold red"
    t.append(f"[{mode.upper()}]", style=mode_style)
    t.append("  ")
    t.append_text(connection_badge(conn))
    t.append("  ")
    t.append(f"ET {now_et:%H:%M:%S}  UTC {now_utc:%H:%M}", style="white")
    t.append("\n")

    net_liq = acct.get("net_liq", "-")
    cash = acct.get("cash", "-")
    bp = acct.get("buying_power", "-")
    pnl = acct.get("daily_pnl")
    pos_count = status.get("positions", {}).get("count", 0)

    if pnl is not None:
        pnl_str = f"{pnl:+.2f}"
        pnl_color = "green" if pnl >= 0 else "red"
        pnl_display = f"[{pnl_color}]{pnl_str}[/{pnl_color}]"
    else:
        pnl_display = "-"

    t.append(f"  NetLiq:{net_liq}  Cash:{cash}  BP:{bp}  P&L:{pnl_display}  Pos:{pos_count}  Univ:{univ}", style="dim white")
    t.append("    Engine: ")

    if status_age < 30:
        age_label = f"[bold green]● LIVE ({int(status_age)}s)[/bold green]"
    else:
        age_label = f"[yellow]● stale {int(status_age)}s[/yellow]"
    t.append_text(Text.from_markup(age_label))

    if paused:
        t.append("  [yellow bold]⏸ PAUSED[/yellow bold]", style="")
    t.append("  [dim]q=quit r=refresh p=pause /=filter Esc=clear[/dim]", style="")
    return Panel(t, style="cyan on #0a1a2a", padding=0)


def positions_panel(rows: list[sqlite3.Row]) -> Panel:
    t = Table(box=box.SIMPLE_HEAD, expand=True, show_edge=False, highlight=True)
    cols = [
        ("Sym", {"style": "bold cyan", "justify": None}),
        ("Side", {"style": None, "justify": None}),
        ("Qty", {"style": None, "justify": "right"}),
        ("Entry", {"style": None, "justify": "right"}),
        ("LMT", {"style": None, "justify": "right"}),
        ("Stop", {"style": None, "justify": "right"}),
        ("Target", {"style": None, "justify": "right"}),
        ("Trail", {"style": None, "justify": "right"}),
        ("Days", {"style": None, "justify": "right"}),
        ("Unrl P&L", {"style": None, "justify": "right"}),
    ]
    for col, kw in cols:
        t.add_column(col, **kw)

    if not rows:
        t.add_row("[dim]- no open positions -[/dim]", *[""] * 9)
    for p in rows:
        side_c = "green" if p["side"] == "long" else "red"
        side_lbl = f"[{side_c}]{p['side'].upper()}[/{side_c}]"
        entry = f"[cyan]{p['entry_price']:.2f}[/cyan]"
        limit_p = f"[cyan]{p['limit_price']:.2f}[/cyan]" if p.get("limit_price") else "-"
        stop = f"[red]{p['stop_price']:.2f}[/red]" if p.get("stop_price") else "-"
        target = f"[green]{p['target_price']:.2f}[/green]" if p.get("target_price") else "-"
        trail = f"[yellow]{p['trailing_stop_price']:.2f}[/yellow]" if p.get("trailing_stop_price") else "-"
        days = str(p.get("holding_days") or 0)
        unreal = p.get("unrealized_pnl")
        if unreal is not None:
            color_style = _pct_color(unreal / (p["entry_price"] * p["qty"] + 1e-9))
            unreal = f"[{color_style}]{unreal:+.2f}[/{color_style}]"
        else:
            unreal = "-"
        t.add_row(
            f"[bold]{p['symbol']}[/bold]",
            side_lbl,
            f"{p['qty']:.0f}",
            entry,
            limit_p,
            stop,
            target,
            trail,
            days,
            unreal,
        )
    return Panel(t, title="[bold]Open Positions ({})[/bold]".format(len(rows)), border_style="blue")


def orders_panel(rows: list[sqlite3.Row]) -> Panel:
    t = Table(box=box.SIMPLE_HEAD, expand=True, show_edge=False)
    for col, kw in [
        ("Sym", {"style": "cyan"}),
        ("Sd", {"justify": None}),
        ("Type", {"style": None}),
        ("Status", {"style": None}),
        ("Qty", {"justify": "right"}),
        ("Price", {"justify": "right"}),
        ("Filled", {"justify": "right"}),
        ("Placed", {"style": "dim"}),
    ]:
        t.add_column(col, **kw)

    if not rows:
        t.add_row("[dim]- no orders -[/dim]", *[""] * 7)
    for o in rows:
        side_c = "green" if o["side"] == "long" else "red"
        placed = (o["placed_at"] or "")[5:16] if o["placed_at"] else "-"
        filled = f"{o['filled_price']:.2f}" if o.get("filled_price") else "-"
        status_c = {"filled": "green", "cancelled": "dim", "submitted": "yellow", "partially_filled": "cyan"}.get(o["status"], "white")
        t.add_row(
            f"[bold]{o['symbol']}[/bold]",
            f"[{side_c}]{o['side'][0].upper()}[/{side_c}]",
            o.get("order_type", ""),
            f"[{status_c}]{o['status']}[/{status_c}]",
            f"{o['qty']:.0f}",
            f"{o.get('price', 0):.2f}",
            filled,
            placed,
        )
    return Panel(t, title="[bold]Recent Orders (last 8)[/bold]", border_style="blue")


def runs_panel(rows: list[sqlite3.Row]) -> Panel:
    t = Table(box=box.SIMPLE_HEAD, expand=True, show_edge=False)
    for col, kw in [
        ("Kind", {"style": "cyan"}),
        ("Started", {"style": "dim"}),
        ("Finished", {"style": "dim"}),
        ("Syms", {"justify": "right"}),
        ("Sigs", {"justify": "right"}),
        ("Ord", {"justify": "right"}),
    ]:
        t.add_column(col, **kw)

    if not rows:
        t.add_row("[dim]- no runs yet -[/dim]", *[""] * 5)
    for r in rows:
        started = (r["started_at"] or "")[5:16] if r["started_at"] else "-"
        if r["finished_at"]:
            finished = r["finished_at"][5:16]
        else:
            finished = "[yellow]running…[/yellow]"
        kind_c = {"SCAN": "cyan", "ORDER": "green", "EOD_REVIEW": "yellow", "UNIVERSE_REFRESH": "magenta"}.get(r["kind"], "white")
        t.add_row(
            f"[{kind_c}]{r['kind']}[/{kind_c}]",
            started,
            finished,
            str(r.get("symbols_processed") or "-"),
            str(r.get("signals_found") or "-"),
            str(r.get("orders_placed") or "-"),
        )
    return Panel(t, title="[bold]Run History[/bold]", border_style="blue")


def schedule_panel(status: dict) -> Panel:
    jobs = status.get("next_runs", {})
    scan_next = _parse_next_run(jobs.get("scan"))
    order_next = _parse_next_run(jobs.get("orders"))
    eod_next = _parse_next_run(jobs.get("eod_review"))
    univ_next = _parse_next_run(jobs.get("universe_refresh"))

    t = Text()
    rows = [
        ("Scan", scan_next, "cyan"),
        ("Orders", order_next, "green"),
        ("EOD Rev", eod_next, "yellow"),
        ("Univ Ref", univ_next, "magenta"),
    ]
    max_label = max(len(label) for label, _, _ in rows)
    for label, val, color in rows:
        t.append(f"{label.ljust(max_label)}  ", style="dim")
        t.append(val + "\n", style=color)
    return Panel(t, title="[bold]Schedule[/bold]", border_style="blue", padding=(0, 1))


def log_panel(lines: list[str]) -> Panel:
    t = Text(overflow="fold")
    error_count = 0
    warn_count = 0
    for line in lines:
        if "ERROR" in line or "FATAL" in line:
            t.append(line + "\n", style="bold red")
            error_count += 1
        elif "WARNING" in line:
            t.append(line + "\n", style="yellow")
            warn_count += 1
        elif "DEBUG" in line:
            t.append(line + "\n", style="dim")
        elif "INFO" in line:
            t.append(line + "\n", style="white")
        else:
            t.append(line + "\n", style="dim")
    footer = ""
    if error_count:
        footer += f"  [bold red]⚠ {error_count} ERR[/bold red]"
    if warn_count:
        footer += f"  [yellow]⚠ {warn_count} WARN[/yellow]"
    return Panel(t, title=f"[bold]Log Tail{footer}[/bold]", border_style="dim grey50")


def exposure_panel(status: dict, univ: int) -> Panel:
    pos = status.get("positions", {})
    pos_count = pos.get("count", 0)
    long_count = pos.get("long", 0)
    short_count = pos.get("short", 0)
    total_positions = max(pos_count, univ)
    exposure_pct = min(pos_count / max(univ, 1) * 100, 100)

    t = Text()
    t.append(f"Positions: {pos_count}  (Long:{long_count}  Short:{short_count})\n", style="cyan")
    t.append(f"Exposure: {exposure_pct:.1f}% of universe\n", style="dim")
    bar = ProgressBar(total=100, completed=exposure_pct, width=40, style="blue")
    t.append(str(bar))
    return Panel(t, title="[bold]Exposure[/bold]", border_style="blue", padding=(0, 1))


# ── layout assembly ────────────────────────────────────────────────────────────
def build_layout(status: dict, univ: int, mode: str, paused: bool, log_filter: str | None, status_age: float | None) -> Layout:
    positions = open_positions()
    orders = recent_orders()
    runs = recent_runs()
    log_lines = tail_log(filter_re=log_filter)

    layout = Layout()
    layout.split_column(
        Layout(name="header", size=4),
        Layout(name="middle"),
        Layout(name="log", size=LOG_LINES + 2),
    )
    layout["middle"].split_row(
        Layout(name="left"),
        Layout(name="right"),
    )
    layout["left"].split_column(
        Layout(name="positions"),
        Layout(name="orders"),
    )
    layout["right"].split_column(
        Layout(name="runs"),
        Layout(name="bottom_right"),
    )
    layout["bottom_right"].split_row(
        Layout(name="schedule"),
        Layout(name="exposure", size=7),
    )

    layout["header"].update(header_panel(status, univ, mode, paused, status_age))
    layout["positions"].update(positions_panel(positions))
    layout["orders"].update(orders_panel(orders))
    layout["runs"].update(runs_panel(runs))
    layout["schedule"].update(schedule_panel(status))
    layout["exposure"].update(exposure_panel(status, univ))
    layout["log"].update(log_panel(log_lines))
    return layout


# ── main loop ─────────────────────────────────────────────────────────────────
import threading
import queue

def main() -> None:
    settings = load_settings()
    mode = settings.connection.mode
    console = Console()

    paused = False
    log_filter: str | None = None
    cmd_queue: queue.Queue[str] = queue.Queue()

    def _input_thread():
        while True:
            try:
                key = console.input("\n")
                cmd_queue.put(key.strip().lower())
            except (EOFError, OSError):
                break

    t = threading.Thread(target=_input_thread, daemon=True)
    t.start()

    with Live(console=console, refresh_per_second=2, screen=True) as live:
        while True:
            status, status_age = load_engine_status()
            univ = universe_count()
            live.update(build_layout(status, univ, mode, paused, log_filter, status_age))

            try:
                cmd = cmd_queue.get_nowait()
            except queue.Empty:
                pass
            else:
                if cmd in ("q", "quit", "exit"):
                    break
                elif cmd == "r":
                    pass
                elif cmd == "p":
                    paused = not paused
                elif cmd.startswith("/"):
                    log_filter = cmd[1:] or None
                elif cmd in ("esc",):
                    log_filter = None

            time.sleep(REFRESH_SECS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
