"""Background thread that monitors an open position and closes on SL/TP."""
from __future__ import annotations
import threading
import time
from datetime import datetime
from typing import Callable, Optional

from .broker.base_broker import BaseBroker, Position, TradeResult


class PositionMonitor:
    def __init__(
        self,
        broker: BaseBroker,
        position: Position,
        poll_interval: int = 60,
        on_close: Optional[Callable[[TradeResult], None]] = None,
    ):
        self._broker = broker
        self._position = position
        self._poll_interval = poll_interval
        self._on_close = on_close
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def _run(self) -> None:
        pos = self._position
        while not self._stop_event.is_set():
            try:
                price = self._broker.get_price(pos.pair)
                hit_sl = self._check_sl(price)
                hit_tp = self._check_tp(price)

                if hit_sl or hit_tp:
                    reason = "sl" if hit_sl else "tp"
                    result = self._broker.close_order(pos.order_id, reason=reason)
                    if self._on_close:
                        self._on_close(result)
                    return
            except Exception as e:
                print(f"[Monitor] Error checking position {pos.order_id}: {e}")

            self._stop_event.wait(self._poll_interval)

    def _check_sl(self, price: float) -> bool:
        pos = self._position
        if pos.action == "LONG":
            return price <= pos.sl_price
        return price >= pos.sl_price

    def _check_tp(self, price: float) -> bool:
        pos = self._position
        if pos.action == "LONG":
            return price >= pos.tp_price
        return price <= pos.tp_price
