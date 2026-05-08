"""Direct MT5 Python library broker — Windows only."""
from __future__ import annotations
import platform
from .base_broker import BaseBroker, Order, Position, TradeResult


class MT5DirectBroker(BaseBroker):
    def __init__(self):
        if platform.system() != "Windows":
            raise RuntimeError(
                "MT5 Direct requires Windows. On Mac, use 'MT5 via Wine' instead."
            )
        import MetaTrader5 as mt5
        if not mt5.initialize():
            raise RuntimeError(f"MT5 initialization failed: {mt5.last_error()}")
        self._mt5 = mt5

    def name(self) -> str:
        return "MT5 Direct"

    def get_price(self, pair: str) -> float:
        tick = self._mt5.symbol_info_tick(pair)
        if tick is None:
            raise RuntimeError(f"Could not get price for {pair}")
        return tick.ask

    def open_order(self, order: Order) -> Position:
        mt5 = self._mt5
        price = self.get_price(order.pair)
        pip = self.pip_value(order.pair)

        order_type = mt5.ORDER_TYPE_BUY if order.action == "LONG" else mt5.ORDER_TYPE_SELL
        sl = price - order.sl_pips * pip if order.action == "LONG" else price + order.sl_pips * pip
        tp = price + order.tp_pips * pip if order.action == "LONG" else price - order.tp_pips * pip

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": order.pair,
            "volume": order.lots,
            "type": order_type,
            "price": price,
            "sl": round(sl, 5),
            "tp": round(tp, 5),
            "deviation": 10,
            "magic": 20260101,
            "comment": "TradingAgents",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            raise RuntimeError(f"Order failed: {result.comment}")

        return Position(
            order_id=str(result.order),
            pair=order.pair,
            action=order.action,
            lots=order.lots,
            open_price=result.price,
            sl_price=round(sl, 5),
            tp_price=round(tp, 5),
            opened_at=str(result.request.comment),
            broker="MT5 Direct",
        )

    def close_order(self, order_id: str, reason: str = "manual") -> TradeResult:
        mt5 = self._mt5
        positions = mt5.positions_get(ticket=int(order_id))
        if not positions:
            raise ValueError(f"Position {order_id} not found in MT5")
        pos_info = positions[0]
        close_type = mt5.ORDER_TYPE_SELL if pos_info.type == 0 else mt5.ORDER_TYPE_BUY
        price = self.get_price(pos_info.symbol)
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": pos_info.symbol,
            "volume": pos_info.volume,
            "type": close_type,
            "position": int(order_id),
            "price": price,
            "deviation": 10,
            "magic": 20260101,
            "comment": f"Close:{reason}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        pip = self.pip_value(pos_info.symbol)
        pips = round(pos_info.profit / (pos_info.volume * pip * 100000), 1)
        return TradeResult(
            position=Position(order_id=order_id, pair=pos_info.symbol,
                              action="LONG" if pos_info.type == 0 else "SHORT",
                              lots=pos_info.volume, open_price=pos_info.price_open,
                              sl_price=pos_info.sl, tp_price=pos_info.tp,
                              opened_at=str(pos_info.time), broker="MT5 Direct"),
            close_price=price,
            pips=pips,
            closed_at=str(result.request.comment),
            reason=reason,
        )

    def get_positions(self) -> list[Position]:
        mt5 = self._mt5
        raw = mt5.positions_get() or []
        return [
            Position(
                order_id=str(p.ticket),
                pair=p.symbol,
                action="LONG" if p.type == 0 else "SHORT",
                lots=p.volume,
                open_price=p.price_open,
                sl_price=p.sl,
                tp_price=p.tp,
                opened_at=str(p.time),
                broker="MT5 Direct",
            )
            for p in raw
        ]
