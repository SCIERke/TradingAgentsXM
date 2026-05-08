"""Helpers for instrument-type-aware behaviour (stock vs forex)."""

from __future__ import annotations


def get_instrument_type(config: dict | None = None) -> str:
    if config is not None:
        return config.get("instrument_type", "stock")
    from tradingagents.dataflows.config import get_config
    return get_config().get("instrument_type", "stock")


def is_forex(config: dict | None = None) -> bool:
    return get_instrument_type(config) == "forex"


def get_fundamental_report(state: dict) -> str:
    """Return whichever economic context report is populated for the current mode."""
    return state.get("macro_report", "") or state.get("fundamentals_report", "")


def get_fundamental_label() -> str:
    return "Macro Economic Report" if is_forex() else "Company Fundamentals Report"


def get_researcher_framing(instrument: str) -> dict:
    """Return mode-appropriate terminology for researcher/risk-agent prompts."""
    if is_forex():
        return {
            "bull_role": f"Bull Analyst advocating for going LONG on {instrument} (expecting the base currency to strengthen)",
            "bear_role": f"Bear Analyst arguing for going SHORT on {instrument} or staying FLAT (expecting the base currency to weaken)",
            "bull_focus": (
                "interest rate differentials favouring the base currency, economic momentum, "
                "positive capital flows, technical uptrend, and bullish macro catalysts"
            ),
            "bear_focus": (
                "rate disadvantages, economic weakness in the base economy, risk-off flows, "
                "technical breakdown, or bearish macro catalysts"
            ),
            "bull_counter": "address the bear's macro concerns with rate/flow data and counter with bullish catalysts",
            "bear_counter": "expose over-optimistic rate assumptions and highlight macro/technical weaknesses",
            "action_vocab": "LONG / FLAT / SHORT",
            "instrument_description": f"forex pair {instrument}",
        }
    return {
        "bull_role": f"Bull Analyst advocating for investing in {instrument}",
        "bear_role": f"Bear Analyst making the case against investing in {instrument}",
        "bull_focus": "growth potential, competitive advantages, and positive market indicators",
        "bear_focus": "risks, challenges, financial instability, and negative indicators",
        "bull_counter": "refute the bear's concerns with financial data and competitive strengths",
        "bear_counter": "expose over-optimistic assumptions and highlight company weaknesses",
        "action_vocab": "BUY / HOLD / SELL",
        "instrument_description": f"stock {instrument}",
    }


def get_risk_framing() -> dict:
    """Return mode-appropriate phrasing for risk-agent prompts."""
    if is_forex():
        return {
            "aggressive_role": "champion high-conviction directional trades with wider targets",
            "conservative_role": "protect capital by favouring tighter stops and smaller position sizes",
            "neutral_role": "balance upside potential against downside risk with a scaled entry approach",
            "action_vocab": "LONG / FLAT / SHORT",
        }
    return {
        "aggressive_role": "champion high-reward, high-risk opportunities with bold position sizing",
        "conservative_role": "protect assets and minimise volatility with conservative sizing",
        "neutral_role": "balance growth potential with risk management in a moderate strategy",
        "action_vocab": "BUY / HOLD / SELL",
    }


def get_rating_scale() -> str:
    if is_forex():
        return (
            "- **Strong Long**: High-conviction entry to go long\n"
            "- **Long**: Constructive; gradually build long exposure\n"
            "- **Flat**: Neutral; stay out or hold flat\n"
            "- **Short**: Cautious; gradually build short exposure\n"
            "- **Strong Short**: High-conviction entry to go short"
        )
    return (
        "- **Buy**: Strong conviction to enter or add to position\n"
        "- **Overweight**: Favorable outlook, gradually increase exposure\n"
        "- **Hold**: Maintain current position, no action needed\n"
        "- **Underweight**: Reduce exposure, take partial profits\n"
        "- **Sell**: Exit position or avoid entry"
    )
