"""Risk profile presets and selection UI for the trade command."""
from __future__ import annotations
import questionary

RISK_PROFILES: dict[str, dict] = {
    "conservative": {
        "lot_mode": "fixed",
        "lot_size": 0.01,
        "sl_pips": 80,
        "tp_pips": 80,
        "sl_tp_mode": "fixed",
        "risk_pct": 1.0,
        "note": "Small size, wide SL — suits choppy/uncertain markets. Risk:reward 1:1.",
    },
    "balanced": {
        "lot_mode": "fixed",
        "lot_size": 0.02,
        "sl_pips": 50,
        "tp_pips": 100,
        "sl_tp_mode": "fixed",
        "risk_pct": 1.0,
        "note": "Standard setup with 1:2 risk:reward. Good default for most conditions.",
    },
    "aggressive": {
        "lot_mode": "dynamic",
        "lot_size": 0.05,
        "sl_pips": 30,
        "tp_pips": 150,
        "sl_tp_mode": "dynamic",
        "risk_pct": 2.0,
        "note": "Agent picks SL/TP from analysis. Dynamic lot = 2% account risk. Tight SL — noise can stop you out.",
    },
}


def select_risk_profile() -> dict:
    choice = questionary.select(
        "Risk profile:",
        choices=[
            questionary.Choice(
                f"Conservative  (0.01 lot | SL 80p | TP 80p | fixed | 1:1 R:R)",
                value="conservative",
            ),
            questionary.Choice(
                f"Balanced      (0.02 lot | SL 50p | TP 100p | fixed | 1:2 R:R)",
                value="balanced",
            ),
            questionary.Choice(
                f"Aggressive    (dynamic lot 2% risk | SL/TP set by agent | 1:5 R:R)",
                value="aggressive",
            ),
            questionary.Choice("Custom        (enter your own values)", value="custom"),
        ],
    ).ask()

    if choice is None:
        raise KeyboardInterrupt

    if choice != "custom":
        profile = dict(RISK_PROFILES[choice])
        return profile

    # ── Custom ────────────────────────────────────────────────────────────────
    lot_mode = questionary.select(
        "Lot sizing mode:",
        choices=[
            questionary.Choice("Fixed lot size", value="fixed"),
            questionary.Choice("Dynamic (% of account balance)", value="dynamic"),
        ],
    ).ask() or "fixed"

    if lot_mode == "fixed":
        raw = questionary.text("Lot size:", default="0.01",
                               validate=lambda v: _is_pos_float(v) or "Enter a positive number").ask()
        lot_size = float(raw or "0.01")
        risk_pct = 1.0
    else:
        raw = questionary.text("Risk % per trade:", default="1.0",
                               validate=lambda v: _is_pos_float(v) or "Enter a positive number").ask()
        risk_pct = float(raw or "1.0")
        lot_size = 0.01  # fallback if dynamic calc not possible

    sl_tp_mode = questionary.select(
        "SL/TP mode:",
        choices=[
            questionary.Choice("Fixed pips (you set)", value="fixed"),
            questionary.Choice("Dynamic (agent decides from analysis)", value="dynamic"),
        ],
    ).ask() or "fixed"

    sl_pips, tp_pips = 50, 100
    if sl_tp_mode == "fixed":
        sl_raw = questionary.text("SL pips:", default="50",
                                  validate=lambda v: v.isdigit() and int(v) > 0 or "Positive integer").ask()
        tp_raw = questionary.text("TP pips:", default="100",
                                  validate=lambda v: v.isdigit() and int(v) > 0 or "Positive integer").ask()
        sl_pips = int(sl_raw or "50")
        tp_pips = int(tp_raw or "100")

    return {
        "lot_mode": lot_mode,
        "lot_size": lot_size,
        "sl_pips": sl_pips,
        "tp_pips": tp_pips,
        "sl_tp_mode": sl_tp_mode,
        "risk_pct": risk_pct,
        "note": "Custom profile.",
    }


def _is_pos_float(v: str) -> bool:
    try:
        return float(v) > 0
    except ValueError:
        return False
