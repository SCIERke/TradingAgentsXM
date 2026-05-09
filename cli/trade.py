"""tradingagents trade <TICKER> — autonomous trading command."""
from __future__ import annotations
import os
import sys

import questionary
import typer
from rich.console import Console
from rich.panel import Panel

console = Console()


def trade(
    ticker: str = typer.Argument(..., help="Ticker symbol, e.g. EURUSD or AAPL"),
    config_file: str = typer.Option(None, "--config", "-c", help="Path to config YAML/JSON (optional)"),
):
    """Run analysis and optionally execute a trade for TICKER."""
    from dotenv import load_dotenv
    load_dotenv()

    # ── Q1: Broker ──────────────────────────────────────────────────────────────
    from execution.broker.factory import select_broker
    broker = select_broker()
    console.print(f"[green]Broker:[/green] {broker.name()}")

    # ── Q2: Oversight mode ──────────────────────────────────────────────────────
    oversight = questionary.select(
        "Human oversight:",
        choices=[
            questionary.Choice("Human-in-loop  (show decision, ask before executing)", value="human"),
            questionary.Choice("No Brain Mode  (execute immediately, Telegram alert sent)", value="auto"),
        ],
    ).ask()
    if oversight is None:
        raise typer.Abort()

    # ── Q3: Monitor mode ─────────────────────────────────────────────────────────
    monitor_mode = questionary.select(
        "Monitor mode:",
        choices=[
            questionary.Choice("Rule-based  (SL/TP only — no AI, free)", value="rule"),
            questionary.Choice("AI Monitor  (LLM checks periodically — exits early if signal flips)", value="ai"),
        ],
    ).ask()
    if monitor_mode is None:
        raise typer.Abort()

    react_interval = 240  # minutes
    if monitor_mode == "ai":
        raw = questionary.text(
            "AI check interval in minutes:",
            default="240",
            validate=lambda v: v.isdigit() and int(v) > 0 or "Enter a positive integer",
        ).ask()
        if raw is None:
            raise typer.Abort()
        react_interval = int(raw)
        console.print(f"[dim]AI monitor will check every {react_interval} min[/dim]")

    # ── Start dashboard ──────────────────────────────────────────────────────────
    from web.app import start_in_background
    start_in_background(port=8080)
    console.print("[dim]Dashboard running at http://localhost:8080[/dim]")

    # ── Load config ──────────────────────────────────────────────────────────────
    from tradingagents.default_config import DEFAULT_CONFIG
    cfg = dict(DEFAULT_CONFIG)
    cfg["ticker"] = ticker.upper()

    # Auto-detect instrument type from ticker format
    t = ticker.upper().replace("/", "")
    if len(t) == 6 and t.isalpha():
        cfg["instrument_type"] = "forex"
    else:
        cfg["instrument_type"] = "stock"

    # ── Run analysis ─────────────────────────────────────────────────────────────
    console.print(Panel(
        f"[bold]Analysing [cyan]{ticker.upper()}[/cyan] ({cfg['instrument_type']}) …[/bold]",
        border_style="blue",
    ))

    try:
        from tradingagents.graph.trading_graph import TradingAgentsGraph
        ta = TradingAgentsGraph(debug=False, config=cfg)
        _, state = ta.propagate(ticker.upper(), _today())
    except Exception as exc:
        console.print(f"[red]Analysis failed:[/red] {exc}")
        raise typer.Exit(1)

    decision_text = state.get("final_trade_decision", "") or state.get("portfolio_decision", "")
    if not decision_text:
        console.print("[yellow]No trade decision produced by the agent.[/yellow]")
        raise typer.Exit(0)

    # ── Display decision ─────────────────────────────────────────────────────────
    console.print(Panel(decision_text[:800], title="Agent Decision", border_style="yellow"))

    # ── Human-in-loop approval ───────────────────────────────────────────────────
    if oversight == "human":
        proceed = questionary.confirm("Execute this trade?", default=True).ask()
        if not proceed:
            console.print("[yellow]Trade skipped by user.[/yellow]")
            from web import state as web_state
            web_state.add_decision(ticker.upper(), decision_text, executed=False)
            raise typer.Exit(0)

    # ── Risk guard + execute ─────────────────────────────────────────────────────
    from execution.order_manager import OrderManager
    from execution.risk_guard import RiskGuardError

    mgr = OrderManager(
        broker=broker,
        pair=ticker.upper(),
        lot_size=cfg.get("lot_size", 0.01),
        sl_pips=cfg.get("sl_pips", 50),
        tp_pips=cfg.get("tp_pips", 100),
        max_open_positions=cfg.get("max_open_positions", 1),
    )

    try:
        pos = mgr.execute(decision_text)
    except RiskGuardError as e:
        console.print(f"[yellow]Risk guard blocked:[/yellow] {e}")
        from web import state as web_state
        web_state.add_decision(ticker.upper(), decision_text, executed=False)
        raise typer.Exit(0)
    except Exception as exc:
        console.print(f"[red]Order failed:[/red] {exc}")
        from alerts.telegram_notifier import TelegramNotifier
        TelegramNotifier().send_error(f"Order failed for {ticker}: {exc}")
        raise typer.Exit(1)

    console.print(Panel(
        f"[bold green]{pos.action} {pos.pair}[/bold green] opened @ {pos.open_price:.5f}\n"
        f"SL: {pos.sl_price:.5f} | TP: {pos.tp_price:.5f} | Lots: {pos.lots}",
        title="Trade Opened",
        border_style="green",
    ))

    # ── Telegram alert ───────────────────────────────────────────────────────────
    from alerts.telegram_notifier import TelegramNotifier
    notifier = TelegramNotifier()
    notifier.send_trade_opened(pos)

    # ── Update dashboard state ────────────────────────────────────────────────────
    from web import state as web_state
    web_state.add_position(pos)
    web_state.add_decision(ticker.upper(), decision_text, executed=True)

    # ── Start position monitor ────────────────────────────────────────────────────
    def _on_close(result):
        web_state.remove_position(pos.order_id, result)
        notifier.send_trade_closed(result)
        console.print(Panel(
            f"[bold]{result.position.action} {result.position.pair}[/bold] closed @ {result.close_price:.5f}\n"
            f"P&L: {result.pips:+.1f} pips | Reason: {result.reason}",
            title="Trade Closed",
            border_style="red" if result.pips < 0 else "green",
        ))

    if monitor_mode == "ai":
        from execution.reactive_monitor import ReactiveMonitor
        from tradingagents.llm_clients.factory import create_llm_client

        monitor_llm = create_llm_client(
            cfg["llm_provider"],
            cfg["quick_think_llm"],
            base_url=cfg.get("backend_url"),
        )

        def _on_llm_check(decision):
            emoji = "🤖 EXIT" if decision.action == "EXIT" else "🤖 HOLD"
            console.print(
                f"[dim]{emoji} — {decision.reason} (confidence: {decision.confidence:.0%})[/dim]"
            )
            web_state.add_monitor_event(
                pos.pair, decision.action, decision.reason, decision.confidence
            )
            if decision.action == "EXIT":
                notifier.send_error(
                    f"AI Monitor: EXIT signal for {pos.pair}\n{decision.reason}"
                )

        monitor = ReactiveMonitor(
            broker, pos, monitor_llm, decision_text,
            react_interval=react_interval,
            poll_interval=60,
            on_close=_on_close,
            on_llm_check=_on_llm_check,
        )
        console.print(
            f"[dim]AI Monitor running — SL/TP every 60s, LLM check every {react_interval} min. "
            f"Dashboard: http://localhost:8080[/dim]"
        )
    else:
        from execution.position_monitor import PositionMonitor
        monitor = PositionMonitor(broker, pos, poll_interval=60, on_close=_on_close)
        console.print(
            f"[dim]Rule-based monitor running (SL/TP checks every 60s). Dashboard: http://localhost:8080[/dim]"
        )

    monitor.start()

    # Keep main thread alive until monitor closes position or user interrupts
    try:
        monitor._thread.join()
    except KeyboardInterrupt:
        monitor.stop()
        console.print("\n[yellow]Monitoring stopped. Position remains open in broker.[/yellow]")


def _today() -> str:
    from datetime import date
    return date.today().strftime("%Y-%m-%d")
