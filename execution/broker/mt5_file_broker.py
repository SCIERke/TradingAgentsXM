"""File-bridge broker for MT5 via Wine on Mac.

Python writes order.json into ~/mt5_bridge/. The TradingAgentsEA.mq5
Expert Advisor running inside MT5 (via Wine/Whisky) polls the file every
2 seconds, executes the trade, and writes status.json back.
"""
from __future__ import annotations
import json
import os
import time
from datetime import datetime

import yfinance as yf

from .base_broker import BaseBroker, Order, Position, TradeResult


def _bridge_dir() -> str:
    path = os.environ.get("MT5_BRIDGE_PATH", os.path.expanduser("~/mt5_bridge"))
    os.makedirs(path, exist_ok=True)
    return path


def _pair_to_yf(pair: str) -> str:
    p = pair.upper().replace("/", "").replace("=X", "")
    return f"{p}=X" if len(p) == 6 else pair


class MT5FileBroker(BaseBroker):
    TIMEOUT = 15  # seconds to wait for EA to respond

    def name(self) -> str:
        return "MT5 (Wine/File bridge)"

    def get_price(self, pair: str) -> float:
        ticker = yf.Ticker(_pair_to_yf(pair))
        data = ticker.history(period="1d", interval="1m")
        if data.empty:
            raise RuntimeError(f"Could not fetch price for {pair}")
        return float(data["Close"].iloc[-1])

    def open_order(self, order: Order) -> Position:
        bridge = _bridge_dir()
        order_path = os.path.join(bridge, "order.json")
        status_path = os.path.join(bridge, "status.json")

        # Clear any stale status
        if os.path.exists(status_path):
            os.remove(status_path)

        payload = {
            "action": order.action,
            "pair": order.pair,
            "lots": order.lots,
            "sl_pips": order.sl_pips,
            "tp_pips": order.tp_pips,
            "timestamp": order.timestamp,
            "processed": False,
        }
        with open(order_path, "w") as f:
            json.dump(payload, f)

        # Wait for EA to respond
        deadline = time.time() + self.TIMEOUT
        while time.time() < deadline:
            if os.path.exists(status_path):
                with open(status_path) as f:
                    status = json.load(f)
                if status.get("status") == "filled":
                    pip = self.pip_value(order.pair)
                    price = status["open_price"]
                    if order.action == "LONG":
                        sl = price - order.sl_pips * pip
                        tp = price + order.tp_pips * pip
                    else:
                        sl = price + order.sl_pips * pip
                        tp = price - order.tp_pips * pip
                    return Position(
                        order_id=str(status["order_id"]),
                        pair=order.pair,
                        action=order.action,
                        lots=order.lots,
                        open_price=price,
                        sl_price=round(sl, 5),
                        tp_price=round(tp, 5),
                        opened_at=datetime.now().isoformat(),
                        broker="MT5",
                    )
            time.sleep(0.5)

        raise TimeoutError("MT5 EA did not respond within timeout. Is the EA running in MT5?")

    def close_order(self, order_id: str, reason: str = "manual") -> TradeResult:
        bridge = _bridge_dir()
        order_path = os.path.join(bridge, "order.json")
        status_path = os.path.join(bridge, "status.json")

        if os.path.exists(status_path):
            os.remove(status_path)

        with open(order_path, "w") as f:
            json.dump({"action": "CLOSE", "order_id": int(order_id), "processed": False}, f)

        deadline = time.time() + self.TIMEOUT
        while time.time() < deadline:
            if os.path.exists(status_path):
                with open(status_path) as f:
                    status = json.load(f)
                if status.get("status") == "closed":
                    return TradeResult(
                        position=Position(order_id=order_id, pair="", action="", lots=0,
                                          open_price=0, sl_price=0, tp_price=0,
                                          opened_at="", broker="MT5"),
                        close_price=status.get("close_price", 0),
                        pips=status.get("pips", 0),
                        closed_at=datetime.now().isoformat(),
                        reason=reason,
                    )
            time.sleep(0.5)

        raise TimeoutError("MT5 EA did not respond to close request.")

    def get_positions(self) -> list[Position]:
        # Positions are tracked by the EA; we read the last status
        return []
