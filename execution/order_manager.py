"""Parse agent decision → Order → Position via broker."""
from __future__ import annotations
import re
from datetime import datetime

from .broker.base_broker import BaseBroker, Order, Position
from .risk_guard import RiskGuard, RiskGuardError


def _extract_action(decision_text: str) -> str:
    """Pull LONG / SHORT / FLAT out of the final_trade_decision string."""
    upper = decision_text.upper()
    # Try structured keywords first
    for keyword in ("STRONG LONG", "LONG", "STRONG SHORT", "SHORT", "FLAT", "HOLD"):
        if keyword in upper:
            if keyword in ("LONG", "STRONG LONG"):
                return "LONG"
            if keyword in ("SHORT", "STRONG SHORT"):
                return "SHORT"
            return "FLAT"
    # Fallback: BUY → LONG, SELL → SHORT
    if "BUY" in upper:
        return "LONG"
    if "SELL" in upper:
        return "SHORT"
    return "FLAT"


class OrderManager:
    def __init__(
        self,
        broker: BaseBroker,
        pair: str,
        lot_size: float = 0.01,
        sl_pips: int = 50,
        tp_pips: int = 100,
        max_open_positions: int = 1,
    ):
        self._broker = broker
        self._pair = pair
        self._lot_size = lot_size
        self._sl_pips = sl_pips
        self._tp_pips = tp_pips
        self._guard = RiskGuard(broker, max_open_positions)

    def execute(self, decision_text: str) -> Position:
        action = _extract_action(decision_text)
        self._guard.check(action)

        order = Order(
            pair=self._pair,
            action=action,
            lots=self._lot_size,
            sl_pips=self._sl_pips,
            tp_pips=self._tp_pips,
            timestamp=datetime.now().isoformat(),
        )
        return self._broker.open_order(order)
