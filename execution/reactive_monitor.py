"""Reactive position monitor — adds a lightweight LLM check on top of SL/TP math."""
from __future__ import annotations
import time
from datetime import datetime
from typing import Any, Callable, Optional

import yfinance as yf

from .broker.base_broker import BaseBroker, Position, TradeResult
from .monitor_schema import MonitorDecision
from .position_monitor import PositionMonitor
from tradingagents.agents.utils.structured import bind_structured


def _pair_to_yf(pair: str) -> str:
    p = pair.upper().replace("/", "").replace("=X", "")
    return f"{p}=X" if len(p) == 6 else pair


def _fetch_ohlcv(pair: str) -> str:
    """Return last 6 × 1h candles as a compact text table."""
    try:
        df = yf.download(_pair_to_yf(pair), period="6h", interval="1h", progress=False, auto_adjust=True)
        if df.empty:
            return "No recent OHLCV data available."
        rows = []
        for ts, row in df.tail(6).iterrows():
            rows.append(
                f"  {ts.strftime('%H:%M')}  O={row['Open']:.5f}  H={row['High']:.5f}"
                f"  L={row['Low']:.5f}  C={row['Close']:.5f}"
            )
        return "\n".join(rows)
    except Exception:
        return "OHLCV fetch failed."


def _build_prompt(pos: Position, current_price: float, original_decision: str) -> str:
    pip = 0.01 if "JPY" in pos.pair.upper() else 0.0001
    raw = (current_price - pos.open_price) if pos.action == "LONG" else (pos.open_price - current_price)
    pips = round(raw / pip, 1)
    ohlcv = _fetch_ohlcv(pos.pair)

    return (
        f"You are a position management agent monitoring an open trade.\n\n"
        f"Position: {pos.action} {pos.pair}\n"
        f"Entry: {pos.open_price:.5f} | Current: {current_price:.5f} | P&L: {pips:+.1f} pips\n"
        f"SL: {pos.sl_price:.5f} | TP: {pos.tp_price:.5f}\n"
        f"Opened: {pos.opened_at}\n\n"
        f"Recent price action (1h candles, last 6):\n{ohlcv}\n\n"
        f"Original trade rationale (summary):\n{original_decision[:600]}\n\n"
        "Should this position be HELD or EXITED early?\n"
        "Only recommend EXIT if the original rationale has clearly broken down.\n"
        "Respond with action=HOLD or action=EXIT, a one-sentence reason, and a confidence score 0.0-1.0."
    )


class ReactiveMonitor(PositionMonitor):
    """Position monitor that adds a periodic LLM HOLD/EXIT check."""

    def __init__(
        self,
        broker: BaseBroker,
        position: Position,
        llm: Any,
        original_decision: str,
        react_interval: int = 240,  # minutes
        poll_interval: int = 60,
        on_close: Optional[Callable[[TradeResult], None]] = None,
        on_llm_check: Optional[Callable[[MonitorDecision], None]] = None,
    ):
        super().__init__(broker, position, poll_interval, on_close)
        self._llm = llm
        self._structured_llm = bind_structured(llm, MonitorDecision, "ReactiveMonitor")
        self._original_decision = original_decision
        self._react_interval_secs = react_interval * 60
        self._last_llm_check: float = 0.0
        self._on_llm_check = on_llm_check

    def _run(self) -> None:
        pos = self._position
        while not self._stop_event.is_set():
            try:
                price = self._broker.get_price(pos.pair)

                # Fast path: SL/TP math (every poll_interval)
                if self._check_sl(price):
                    result = self._broker.close_order(pos.order_id, reason="sl")
                    if self._on_close:
                        self._on_close(result)
                    return
                if self._check_tp(price):
                    result = self._broker.close_order(pos.order_id, reason="tp")
                    if self._on_close:
                        self._on_close(result)
                    return

                # Slow path: LLM HOLD/EXIT check
                now = time.time()
                if now - self._last_llm_check >= self._react_interval_secs:
                    self._last_llm_check = now
                    decision = self._llm_check(price)
                    if self._on_llm_check:
                        self._on_llm_check(decision)
                    if decision.action == "EXIT":
                        result = self._broker.close_order(pos.order_id, reason="agent_exit")
                        if self._on_close:
                            self._on_close(result)
                        return

            except Exception as e:
                print(f"[ReactiveMonitor] Error: {e}")

            self._stop_event.wait(self._poll_interval)

    def _llm_check(self, current_price: float) -> MonitorDecision:
        prompt = _build_prompt(self._position, current_price, self._original_decision)
        try:
            if self._structured_llm is not None:
                result = self._structured_llm.invoke(prompt)
                if isinstance(result, MonitorDecision):
                    return result
        except Exception as e:
            print(f"[ReactiveMonitor] Structured LLM failed ({e}), trying free-text fallback")

        # Free-text fallback: look for HOLD/EXIT keyword in response
        try:
            response = self._llm.invoke(prompt)
            text = response.content.upper()
            action = "EXIT" if "EXIT" in text else "HOLD"
            return MonitorDecision(action=action, reason="(parsed from free-text response)", confidence=0.5)
        except Exception as e:
            print(f"[ReactiveMonitor] LLM check failed entirely ({e}), defaulting to HOLD")
            return MonitorDecision(action="HOLD", reason="LLM unavailable", confidence=0.0)
