"""Shared in-memory dashboard state, persisted to disk."""
from __future__ import annotations
import json
import os
import threading
from datetime import datetime
from typing import Any

from execution.broker.base_broker import Position, TradeResult

_STATE_PATH = os.path.expanduser("~/.tradingagents/dashboard_state.json")
_lock = threading.Lock()

_state: dict[str, Any] = {
    "open_positions": [],
    "closed_trades": [],
    "decisions": [],
    "last_updated": "",
}


def _persist() -> None:
    os.makedirs(os.path.dirname(_STATE_PATH), exist_ok=True)
    with open(_STATE_PATH, "w") as f:
        json.dump(_state, f, indent=2)


def load_from_disk() -> None:
    if os.path.exists(_STATE_PATH):
        with open(_STATE_PATH) as f:
            _state.update(json.load(f))


def get_state() -> dict:
    with _lock:
        return dict(_state)


def add_position(pos: Position) -> None:
    with _lock:
        _state["open_positions"].append(pos.__dict__)
        _state["last_updated"] = datetime.now().isoformat()
        _persist()


def remove_position(order_id: str, result: TradeResult) -> None:
    with _lock:
        _state["open_positions"] = [
            p for p in _state["open_positions"] if p["order_id"] != order_id
        ]
        _state["closed_trades"].insert(0, {
            **result.position.__dict__,
            "close_price": result.close_price,
            "pips": result.pips,
            "closed_at": result.closed_at,
            "reason": result.reason,
        })
        _state["last_updated"] = datetime.now().isoformat()
        _persist()


def add_decision(ticker: str, decision: str, executed: bool) -> None:
    with _lock:
        _state["decisions"].insert(0, {
            "ticker": ticker,
            "decision": decision,
            "executed": executed,
            "timestamp": datetime.now().isoformat(),
        })
        _state["decisions"] = _state["decisions"][:50]  # keep last 50
        _state["last_updated"] = datetime.now().isoformat()
        _persist()
