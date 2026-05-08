"""Forex macro data fetcher using yfinance proxy tickers."""

from __future__ import annotations

from datetime import datetime
from dateutil.relativedelta import relativedelta
import pandas as pd
import yfinance as yf

from .stockstats_utils import yf_retry

# Macro proxy tickers that give economic context for forex analysis
_GLOBAL_MACRO = {
    "DXY (USD Index)": "DX-Y.NYB",
    "10Y Treasury Yield": "^TNX",
    "2Y Treasury Yield": "^IRX",
    "Gold (safe haven)": "GC=F",
    "Oil (WTI)": "CL=F",
    "VIX (volatility)": "^VIX",
}

# Additional per-currency proxies
_CURRENCY_PROXIES: dict[str, dict[str, str]] = {
    "EUR": {"EUR/USD": "EURUSD=X"},
    "GBP": {"GBP/USD": "GBPUSD=X"},
    "JPY": {"USD/JPY": "USDJPY=X"},
    "CHF": {"USD/CHF": "USDCHF=X"},
    "AUD": {"AUD/USD": "AUDUSD=X"},
    "CAD": {"USD/CAD": "USDCAD=X"},
    "NZD": {"NZD/USD": "NZDUSD=X"},
}


def _parse_pair(pair: str) -> tuple[str, str]:
    """Extract base and quote currencies from a pair string like EURUSD or EUR/USD."""
    pair = pair.upper().replace("/", "").replace("=X", "").replace("-", "")
    if len(pair) == 6:
        return pair[:3], pair[3:]
    return pair, ""


def _fetch_single(ticker: str, start: str, end: str) -> str:
    """Fetch close prices for one ticker and return a formatted summary."""
    try:
        obj = yf.Ticker(ticker)
        data = yf_retry(lambda: obj.history(start=start, end=end))
        if data.empty:
            return "N/A"
        closes = data["Close"].dropna()
        if closes.empty:
            return "N/A"
        latest = closes.iloc[-1]
        change = ((closes.iloc[-1] - closes.iloc[0]) / closes.iloc[0]) * 100
        return f"{latest:.4f} (period change: {change:+.2f}%)"
    except Exception:
        return "N/A"


def get_forex_macro_data(
    pair: str,
    curr_date: str,
    look_back_days: int = 14,
) -> str:
    """Fetch macro economic indicators relevant to a forex pair.

    Args:
        pair: Currency pair e.g. 'EURUSD', 'EUR/USD', 'GBPJPY'
        curr_date: Reference date in yyyy-mm-dd format
        look_back_days: How many calendar days to look back

    Returns:
        Formatted report string of macro indicators
    """
    end_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    start_dt = end_dt - relativedelta(days=look_back_days)
    start = start_dt.strftime("%Y-%m-%d")
    end = curr_date

    base, quote = _parse_pair(pair)

    lines = [
        f"# Forex Macro Report for {pair.upper()}",
        f"# Period: {start} to {end}",
        f"# Base currency: {base}  |  Quote currency: {quote}",
        "",
        "## Global Macro Indicators",
    ]

    for label, ticker in _GLOBAL_MACRO.items():
        val = _fetch_single(ticker, start, end)
        lines.append(f"- {label} ({ticker}): {val}")

    lines.append("")
    lines.append("## Related Currency Pairs (context)")

    for ccy in [base, quote]:
        proxies = _CURRENCY_PROXIES.get(ccy, {})
        for label, ticker in proxies.items():
            val = _fetch_single(ticker, start, end)
            lines.append(f"- {label}: {val}")

    lines.extend([
        "",
        "## Interpretation Notes",
        "- Rising DXY = stronger USD (bearish for EUR/USD, GBP/USD, AUD/USD; bullish for USD/JPY, USD/CAD)",
        "- Rising 10Y yield = risk-on / higher rate expectations → often USD-positive",
        "- Rising Gold = risk-off or inflation fears → often USD-negative",
        "- Rising VIX = risk-off → typically favours safe havens (USD, JPY, CHF)",
        "- Rising Oil = positive for commodity currencies (CAD, AUD, NOK)",
    ])

    return "\n".join(lines)
