from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Order:
    pair: str
    action: str          # "LONG" | "SHORT" | "FLAT"
    lots: float
    sl_pips: int
    tp_pips: int
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class Position:
    order_id: str
    pair: str
    action: str
    lots: float
    open_price: float
    sl_price: float
    tp_price: float
    opened_at: str
    broker: str


@dataclass
class TradeResult:
    position: Position
    close_price: float
    pips: float
    closed_at: str
    reason: str          # "tp" | "sl" | "manual"


class BaseBroker(ABC):
    @abstractmethod
    def open_order(self, order: Order) -> Position: ...

    @abstractmethod
    def close_order(self, order_id: str) -> TradeResult: ...

    @abstractmethod
    def get_positions(self) -> list[Position]: ...

    @abstractmethod
    def get_price(self, pair: str) -> float: ...

    @abstractmethod
    def name(self) -> str: ...

    def pip_value(self, pair: str) -> float:
        """Return pip size for a pair (0.0001 for most, 0.01 for JPY pairs)."""
        return 0.01 if "JPY" in pair.upper() else 0.0001
