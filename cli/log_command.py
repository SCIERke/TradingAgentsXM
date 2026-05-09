"""tradingagents log — view past trade run history."""
from __future__ import annotations
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich import box

console = Console()


def log_runs(
    tail: int = typer.Option(10, "--tail", "-n", help="Number of recent runs to show"),
    ticker: Optional[str] = typer.Option(None, "--ticker", "-t", help="Filter by ticker symbol"),
):
    """Show history of past trade command runs from the journal."""
    from execution.trade_journal import TradeJournal
    journal = TradeJournal()
    entries = journal.load(ticker=ticker, tail=tail)

    if not entries:
        console.print("[yellow]No trade journal entries found.[/yellow]")
        if ticker:
            console.print(f"[dim]Filtered by ticker: {ticker.upper()}[/dim]")
        return

    t = Table(box=box.SIMPLE_HEAVY, show_lines=False)
    t.add_column("Run ID", style="dim", no_wrap=True)
    t.add_column("Time", no_wrap=True)
    t.add_column("Ticker", style="bold")
    t.add_column("Decision")
    t.add_column("Exec?")
    t.add_column("Lots")
    t.add_column("SL/TP pips")
    t.add_column("Cost")
    t.add_column("Result")

    for e in reversed(entries):
        ts = e.get("timestamp", "")[:16].replace("T", " ")
        ticker_val = e.get("ticker", "—")
        decision = _short_action(e.get("decision", ""))
        executed = "[green]Yes[/green]" if e.get("executed") else "[dim]No[/dim]"

        order = e.get("order")
        lots = f"{order['lots']}" if order else "—"
        sl_tp = f"{order.get('sl_pips','?')}/{order.get('tp_pips','?')}" if order else "—"

        stats = e.get("llm_stats", {})
        cost = f"${stats['estimated_usd']:.4f}" if stats.get("estimated_usd") is not None else "—"

        pips = e.get("pips")
        reason = e.get("close_reason", "")
        if pips is not None:
            colour = "green" if pips >= 0 else "red"
            result = f"[{colour}]{pips:+.1f}p[/{colour}] ({reason})"
        elif e.get("executed"):
            result = "[dim]open[/dim]"
        else:
            result = "[dim]—[/dim]"

        t.add_row(e.get("run_id", "?"), ts, ticker_val, decision, executed, lots, sl_tp, cost, result)

    console.print(t)
    if ticker:
        console.print(f"[dim]Filtered by: {ticker.upper()} | showing last {len(entries)} entries[/dim]")
    else:
        console.print(f"[dim]Showing last {len(entries)} entries | "
                      f"journal: ~/.tradingagents/trade_journal.jsonl[/dim]")


def _short_action(decision: str) -> str:
    upper = decision.upper()
    for kw in ("STRONG LONG", "LONG", "STRONG SHORT", "SHORT", "FLAT", "BUY", "HOLD", "SELL"):
        if kw in upper:
            return kw.title()
    return decision[:12]
