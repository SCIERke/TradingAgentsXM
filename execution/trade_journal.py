"""Append-only JSONL log of every `tradingagents trade` run."""
from __future__ import annotations
import json
import os
import uuid
from datetime import datetime
from typing import Any, Optional

_JOURNAL_PATH = os.path.expanduser("~/.tradingagents/trade_journal.jsonl")

# Config keys worth snapshotting for reproducibility
_CONFIG_KEYS = (
    "llm_provider", "deep_think_llm", "quick_think_llm",
    "max_debate_rounds", "max_risk_discuss_rounds",
    "instrument_type", "lot_mode", "sl_tp_mode",
)


class TradeJournal:
    def __init__(self, path: str = _JOURNAL_PATH):
        self._path = os.path.expanduser(path)
        os.makedirs(os.path.dirname(self._path), exist_ok=True)

    def record(
        self,
        *,
        ticker: str,
        instrument_type: str,
        broker_name: str,
        oversight: str,
        monitor_mode: str,
        analysts: list[str],
        profile_name: str,
        lot_mode: str,
        sl_tp_mode: str,
        decision_text: str,
        executed: bool,
        position=None,       # execution.broker.base_broker.Position | None
        llm_stats: Optional[dict] = None,
        config: Optional[dict] = None,
    ) -> str:
        run_id = uuid.uuid4().hex[:8]
        entry: dict[str, Any] = {
            "run_id": run_id,
            "timestamp": datetime.now().isoformat(),
            "ticker": ticker,
            "instrument_type": instrument_type,
            "broker": broker_name,
            "oversight": oversight,
            "monitor_mode": monitor_mode,
            "analysts": analysts,
            "profile": profile_name,
            "lot_mode": lot_mode,
            "sl_tp_mode": sl_tp_mode,
            "decision": decision_text[:600],
            "executed": executed,
        }

        if position is not None:
            entry["order"] = {
                "action": position.action,
                "lots": position.lots,
                "open_price": position.open_price,
                "sl_price": position.sl_price,
                "tp_price": position.tp_price,
                "sl_pips": round(abs(position.open_price - position.sl_price) /
                                 (0.01 if "JPY" in ticker.upper() else 0.0001)),
                "tp_pips": round(abs(position.open_price - position.tp_price) /
                                 (0.01 if "JPY" in ticker.upper() else 0.0001)),
            }

        if llm_stats:
            entry["llm_stats"] = llm_stats

        if config:
            entry["config_snapshot"] = {k: config[k] for k in _CONFIG_KEYS if k in config}

        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        return run_id

    def annotate_close(self, run_id: str, close_price: float, pips: float, reason: str) -> None:
        """Add close details to an existing journal entry by run_id."""
        if not os.path.exists(self._path):
            return
        lines = []
        with open(self._path, encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    if entry.get("run_id") == run_id:
                        entry["close_price"] = close_price
                        entry["pips"] = pips
                        entry["close_reason"] = reason
                        entry["closed_at"] = datetime.now().isoformat()
                        line = json.dumps(entry, ensure_ascii=False) + "\n"
                except (json.JSONDecodeError, KeyError):
                    pass
                lines.append(line)
        tmp = self._path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.writelines(lines)
        os.replace(tmp, self._path)

    def load(self, ticker: Optional[str] = None, tail: int = 50) -> list[dict]:
        if not os.path.exists(self._path):
            return []
        entries = []
        with open(self._path, encoding="utf-8") as f:
            for line in f:
                try:
                    e = json.loads(line)
                    if ticker is None or e.get("ticker", "").upper() == ticker.upper():
                        entries.append(e)
                except json.JSONDecodeError:
                    pass
        return entries[-tail:]
