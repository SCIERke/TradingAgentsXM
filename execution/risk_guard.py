"""Safety checks before placing a new order."""
from __future__ import annotations
from .broker.base_broker import BaseBroker


class RiskGuardError(Exception):
    pass


class RiskGuard:
    def __init__(self, broker: BaseBroker, max_open_positions: int = 1):
        self._broker = broker
        self._max_open = max_open_positions

    def check(self, action: str) -> None:
        if action == "FLAT":
            raise RiskGuardError("Action is FLAT — no trade to place.")

        positions = self._broker.get_positions()
        if len(positions) >= self._max_open:
            raise RiskGuardError(
                f"Max open positions reached ({len(positions)}/{self._max_open}). Close existing positions first."
            )
