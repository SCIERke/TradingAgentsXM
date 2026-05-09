"""tradingagents trade <TICKER> — autonomous trading command."""
from __future__ import annotations
from datetime import date

import questionary
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

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

    react_interval = 240
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

    # ── Load config + detect instrument type ─────────────────────────────────────
    from tradingagents.default_config import DEFAULT_CONFIG
    cfg = dict(DEFAULT_CONFIG)
    cfg["ticker"] = ticker.upper()

    t = ticker.upper().replace("/", "")
    cfg["instrument_type"] = "forex" if (len(t) == 6 and t.isalpha()) else "stock"

    # ── Q4: Analyst selection ────────────────────────────────────────────────────
    from cli.utils import select_analysts
    selected = select_analysts(cfg["instrument_type"])
    console.print(f"[dim]Analysts: {', '.join(a.value for a in selected)}[/dim]")

    # ── Q5: Risk profile ─────────────────────────────────────────────────────────
    from cli.risk_profiles import select_risk_profile
    profile = select_risk_profile()
    console.print(f"[dim]{profile.get('note', '')}[/dim]")

    # Merge profile into config
    cfg.update({k: v for k, v in profile.items() if k != "note"})

    # ── Start dashboard ──────────────────────────────────────────────────────────
    from web.app import start_in_background
    start_in_background(port=8080)
    console.print("[dim]Dashboard running at http://localhost:8080[/dim]")

    # ── Run analysis (with cost tracking) ────────────────────────────────────────
    from cli.stats_handler import StatsCallbackHandler
    from execution.cost_tracker import CostTracker

    stats_handler = StatsCallbackHandler()
    cost_tracker = CostTracker(cfg["deep_think_llm"])

    console.print(Panel(
        f"[bold]Analysing [cyan]{ticker.upper()}[/cyan] ({cfg['instrument_type']}) …[/bold]",
        border_style="blue",
    ))

    try:
        from tradingagents.graph.trading_graph import TradingAgentsGraph
        ta = TradingAgentsGraph(
            debug=False,
            config=cfg,
            selected_analysts=selected,
            callbacks=[stats_handler],
        )
        _, state = ta.propagate(ticker.upper(), date.today().strftime("%Y-%m-%d"))
    except Exception as exc:
        console.print(f"[red]Analysis failed:[/red] {exc}")
        raise typer.Exit(1)

    # ── Cost summary ─────────────────────────────────────────────────────────────
    raw_stats = stats_handler.get_stats()
    summary = cost_tracker.summary(raw_stats)
    _show_cost_panel(summary)

    max_cost = cfg.get("max_analysis_cost_usd", 2.0)
    if cost_tracker.exceeds(raw_stats, max_cost):
        console.print(f"[yellow]Warning: analysis cost ~${summary['estimated_usd']:.4f} exceeds "
                      f"max_analysis_cost_usd=${max_cost}[/yellow]")
        if oversight == "human":
            ok = questionary.confirm("Continue anyway?", default=False).ask()
            if not ok:
                console.print("[yellow]Aborted by cost guardrail.[/yellow]")
                raise typer.Exit(0)
        else:
            from alerts.telegram_notifier import TelegramNotifier
            TelegramNotifier().send_error(
                f"Cost guardrail: analysis for {ticker} cost ~${summary['estimated_usd']:.4f} "
                f"(limit ${max_cost}). Continuing in No Brain Mode."
            )

    # ── Extract decision ─────────────────────────────────────────────────────────
    decision_text = state.get("final_trade_decision", "") or state.get("portfolio_decision", "")
    if not decision_text:
        console.print("[yellow]No trade decision produced by the agent.[/yellow]")
        raise typer.Exit(0)

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
        lot_mode=cfg.get("lot_mode", "fixed"),
        risk_pct=cfg.get("risk_pct", 1.0),
        sl_tp_mode=cfg.get("sl_tp_mode", "fixed"),
        account_balance=cfg.get("account_balance", 10_000.0),
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

    sl_tp_label = "agent-set" if cfg.get("sl_tp_mode") == "dynamic" else "fixed"
    lot_label = f"dynamic ({cfg.get('risk_pct', 1.0)}% risk)" if cfg.get("lot_mode") == "dynamic" else "fixed"
    console.print(Panel(
        f"[bold green]{pos.action} {pos.pair}[/bold green] opened @ {pos.open_price:.5f}\n"
        f"SL: {pos.sl_price:.5f} | TP: {pos.tp_price:.5f}\n"
        f"Lots: {pos.lots} ({lot_label}) | SL/TP: {sl_tp_label}",
        title="Trade Opened",
        border_style="green",
    ))

    # ── Telegram + dashboard ──────────────────────────────────────────────────────
    from alerts.telegram_notifier import TelegramNotifier
    notifier = TelegramNotifier()
    notifier.send_trade_opened(pos)

    from web import state as web_state
    web_state.add_position(pos)
    web_state.add_decision(ticker.upper(), decision_text, executed=True)

    # ── Start monitor ─────────────────────────────────────────────────────────────
    def _on_close(result):
        web_state.remove_position(pos.order_id, result)
        notifier.send_trade_closed(result)
        console.print(Panel(
            f"[bold]{result.position.action} {result.position.pair}[/bold] "
            f"closed @ {result.close_price:.5f}\n"
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
            emoji = "EXIT" if decision.action == "EXIT" else "HOLD"
            console.print(
                f"[dim][AI Monitor] {emoji} — {decision.reason} "
                f"(confidence: {decision.confidence:.0%})[/dim]"
            )
            web_state.add_monitor_event(
                pos.pair, decision.action, decision.reason, decision.confidence
            )
            if decision.action == "EXIT":
                notifier.send_error(
                    f"AI Monitor EXIT signal for {pos.pair}\n{decision.reason}"
                )

        monitor = ReactiveMonitor(
            broker, pos, monitor_llm, decision_text,
            react_interval=react_interval,
            poll_interval=60,
            on_close=_on_close,
            on_llm_check=_on_llm_check,
        )
        console.print(
            f"[dim]AI Monitor: SL/TP every 60s + LLM check every {react_interval} min. "
            f"Dashboard: http://localhost:8080[/dim]"
        )
    else:
        from execution.position_monitor import PositionMonitor
        monitor = PositionMonitor(broker, pos, poll_interval=60, on_close=_on_close)
        console.print(
            "[dim]Rule-based monitor: SL/TP checks every 60s. "
            "Dashboard: http://localhost:8080[/dim]"
        )

    monitor.start()

    try:
        monitor._thread.join()
    except KeyboardInterrupt:
        monitor.stop()
        console.print("\n[yellow]Monitoring stopped. Position remains open in broker.[/yellow]")


def _show_cost_panel(summary: dict) -> None:
    t = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    t.add_column("key", style="dim")
    t.add_column("val")
    t.add_row("LLM calls", str(summary.get("llm_calls", 0)))
    t.add_row("Tool calls", str(summary.get("tool_calls", 0)))
    t.add_row("Tokens in", f"{summary.get('tokens_in', 0):,}")
    t.add_row("Tokens out", f"{summary.get('tokens_out', 0):,}")
    t.add_row("Est. cost", f"~${summary.get('estimated_usd', 0):.4f}")
    console.print(Panel(t, title="Analysis Cost", border_style="dim"))
