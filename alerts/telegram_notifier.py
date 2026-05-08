"""Telegram alert sender using python-telegram-bot (sync wrapper)."""
from __future__ import annotations
import os
import asyncio
from typing import Optional

try:
    from telegram import Bot
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False

from execution.broker.base_broker import Position, TradeResult


def _send(token: str, chat_id: str, text: str) -> None:
    async def _inner():
        bot = Bot(token=token)
        await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
    asyncio.run(_inner())


class TelegramNotifier:
    def __init__(self):
        self._token: Optional[str] = os.environ.get("TELEGRAM_BOT_TOKEN")
        self._chat_id: Optional[str] = os.environ.get("TELEGRAM_CHAT_ID")
        self._enabled = _AVAILABLE and bool(self._token) and bool(self._chat_id)

    def _send(self, text: str) -> None:
        if not self._enabled:
            return
        try:
            _send(self._token, self._chat_id, text)
        except Exception as e:
            print(f"[Telegram] Failed to send alert: {e}")

    def send_trade_opened(self, pos: Position) -> None:
        direction = "LONG" if pos.action == "LONG" else "SHORT"
        emoji = "🟢" if direction == "LONG" else "🔴"
        self._send(
            f"{emoji} <b>{direction} {pos.pair}</b> opened @ {pos.open_price:.5f}\n"
            f"SL: {pos.sl_price:.5f} | TP: {pos.tp_price:.5f}\n"
            f"Lots: {pos.lots} | Broker: {pos.broker}"
        )

    def send_trade_closed(self, result: TradeResult) -> None:
        pos = result.position
        pips = result.pips
        emoji = "✅" if pips >= 0 else "❌"
        reason_label = {"tp": "TP hit", "sl": "SL hit", "manual": "Manual close"}.get(result.reason, result.reason)
        self._send(
            f"{emoji} <b>{pos.action} {pos.pair}</b> closed @ {result.close_price:.5f}\n"
            f"P&L: {pips:+.1f} pips | Reason: {reason_label}\n"
            f"Opened: {pos.open_price:.5f} → Closed: {result.close_price:.5f}"
        )

    def send_error(self, message: str) -> None:
        self._send(f"⚠️ <b>TradingAgents Error</b>\n{message}")
