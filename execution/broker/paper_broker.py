from __future__ import annotations
import json
import os
import uuid
from datetime import datetime

import yfinance as yf

from .base_broker import BaseBroker, Order, Position, TradeResult


_STATE_PATH = os.path.expanduser("~/.tradingagents/paper_positions.json")


def _pair_to_yf(pair: str) -> str:
    p = pair.upper().replace("/", "").replace("=X", "")
    if len(p) == 6:
        return f"{p}=X"
    return pair


def _load() -> dict:
    if os.path.exists(_STATE_PATH):
        with open(_STATE_PATH) as f:
            return json.load(f)
    return {"positions": []}


def _save(state: dict) -> None:
    os.makedirs(os.path.dirname(_STATE_PATH), exist_ok=True)
    with open(_STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


class PaperBroker(BaseBroker):
    def name(self) -> str:
        return "Paper"

    def get_price(self, pair: str) -> float:
        ticker = yf.Ticker(_pair_to_yf(pair))
        data = ticker.history(period="1d", interval="1m")
        if data.empty:
            raise RuntimeError(f"Could not fetch price for {pair}")
        return float(data["Close"].iloc[-1])

    def open_order(self, order: Order) -> Position:
        price = self.get_price(order.pair)
        pip = self.pip_value(order.pair)

        if order.action == "LONG":
            sl = price - order.sl_pips * pip
            tp = price + order.tp_pips * pip
        else:  # SHORT
            sl = price + order.sl_pips * pip
            tp = price - order.tp_pips * pip

        pos = Position(
            order_id=str(uuid.uuid4())[:8],
            pair=order.pair,
            action=order.action,
            lots=order.lots,
            open_price=price,
            sl_price=round(sl, 5),
            tp_price=round(tp, 5),
            opened_at=datetime.now().isoformat(),
            broker="Paper",
        )
        state = _load()
        state["positions"].append(pos.__dict__)
        _save(state)
        return pos

    def close_order(self, order_id: str, reason: str = "manual") -> TradeResult:
        state = _load()
        for i, p in enumerate(state["positions"]):
            if p["order_id"] == order_id:
                pos = Position(**p)
                price = self.get_price(pos.pair)
                pip = self.pip_value(pos.pair)
                raw = (price - pos.open_price) if pos.action == "LONG" else (pos.open_price - price)
                pips = round(raw / pip, 1)
                state["positions"].pop(i)
                _save(state)
                return TradeResult(
                    position=pos,
                    close_price=price,
                    pips=pips,
                    closed_at=datetime.now().isoformat(),
                    reason=reason,
                )
        raise ValueError(f"Position {order_id} not found")

    def get_positions(self) -> list[Position]:
        return [Position(**p) for p in _load()["positions"]]
