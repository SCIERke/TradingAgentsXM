"""Parse agent decision → Order → Position via broker."""
from __future__ import annotations
import re
from datetime import datetime

from .broker.base_broker import BaseBroker, Order, Position
from .risk_guard import RiskGuard, RiskGuardError

# Regex patterns for extracting SL/TP price levels from rendered decision text
_SL_RE = re.compile(r'\*\*Stop Loss\*\*:\s*([\d.]+)')
_TP_RE = re.compile(r'\*\*(?:Take Profit|Price Target)\*\*:\s*([\d.]+)')


def _extract_action(decision_text: str) -> str:
    """Pull LONG / SHORT / FLAT out of the final_trade_decision string."""
    upper = decision_text.upper()
    for keyword in ("STRONG LONG", "LONG", "STRONG SHORT", "SHORT", "FLAT", "HOLD"):
        if keyword in upper:
            if keyword in ("LONG", "STRONG LONG"):
                return "LONG"
            if keyword in ("SHORT", "STRONG SHORT"):
                return "SHORT"
            return "FLAT"
    if "BUY" in upper:
        return "LONG"
    if "SELL" in upper:
        return "SHORT"
    return "FLAT"


def _extract_sl_tp_dynamic(
    decision_text: str,
    open_price: float,
    pip_value: float,
    fallback_sl: int,
    fallback_tp: int,
) -> tuple[int, int]:
    """Parse SL/TP price levels from decision text and convert to pips."""
    sl_pips = fallback_sl
    tp_pips = fallback_tp

    sl_match = _SL_RE.search(decision_text)
    if sl_match:
        try:
            sl_price = float(sl_match.group(1))
            computed = round(abs(open_price - sl_price) / pip_value)
            if computed > 0:
                sl_pips = computed
        except (ValueError, ZeroDivisionError):
            pass

    tp_match = _TP_RE.search(decision_text)
    if tp_match:
        try:
            tp_price = float(tp_match.group(1))
            computed = round(abs(open_price - tp_price) / pip_value)
            if computed > 0:
                tp_pips = computed
        except (ValueError, ZeroDivisionError):
            pass

    return sl_pips, tp_pips


def _dynamic_lot(
    risk_pct: float,
    sl_pips: int,
    pip_value: float,
    account_balance: float,
) -> float:
    """Calculate lot size based on account risk percentage."""
    try:
        lots = (account_balance * risk_pct / 100) / (sl_pips * pip_value * 100_000)
        return round(max(0.01, min(lots, 100.0)), 2)
    except (ZeroDivisionError, ValueError):
        return 0.01


class OrderManager:
    def __init__(
        self,
        broker: BaseBroker,
        pair: str,
        lot_size: float = 0.01,
        sl_pips: int = 50,
        tp_pips: int = 100,
        max_open_positions: int = 1,
        lot_mode: str = "fixed",
        risk_pct: float = 1.0,
        sl_tp_mode: str = "fixed",
        account_balance: float = 10_000.0,
    ):
        self._broker = broker
        self._pair = pair
        self._lot_size = lot_size
        self._sl_pips = sl_pips
        self._tp_pips = tp_pips
        self._lot_mode = lot_mode
        self._risk_pct = risk_pct
        self._sl_tp_mode = sl_tp_mode
        self._account_balance = account_balance
        self._guard = RiskGuard(broker, max_open_positions)

    def execute(self, decision_text: str) -> Position:
        action = _extract_action(decision_text)
        self._guard.check(action)

        pip_value = self._broker.pip_value(self._pair)

        # Get entry price to compute dynamic SL/TP in pips
        open_price = self._broker.get_price(self._pair)

        # Resolve SL/TP pips
        if self._sl_tp_mode == "dynamic":
            sl_pips, tp_pips = _extract_sl_tp_dynamic(
                decision_text, open_price, pip_value,
                self._sl_pips, self._tp_pips,
            )
        else:
            sl_pips, tp_pips = self._sl_pips, self._tp_pips

        # Resolve lot size
        if self._lot_mode == "dynamic":
            lots = _dynamic_lot(self._risk_pct, sl_pips, pip_value, self._account_balance)
        else:
            lots = self._lot_size

        order = Order(
            pair=self._pair,
            action=action,
            lots=lots,
            sl_pips=sl_pips,
            tp_pips=tp_pips,
            lot_mode=self._lot_mode,
            risk_pct=self._risk_pct,
            timestamp=datetime.now().isoformat(),
        )
        return self._broker.open_order(order)
