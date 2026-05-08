from langchain_core.tools import tool
from typing import Annotated
from tradingagents.dataflows.interface import route_to_vendor


@tool
def get_forex_macro(
    pair: Annotated[str, "Currency pair e.g. EURUSD, GBPUSD, USDJPY"],
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    look_back_days: Annotated[int, "Number of calendar days to look back"] = 14,
) -> str:
    """Retrieve macro economic indicators relevant to a forex currency pair.

    Returns DXY (USD index), treasury yields, gold, oil, VIX, and related
    currency pair performance — the key inputs for interest-rate-differential
    and risk-sentiment analysis in forex trading.

    Args:
        pair: Currency pair e.g. EURUSD, GBPUSD, USDJPY
        curr_date: Current date in yyyy-mm-dd format
        look_back_days: Number of calendar days to look back (default 14)

    Returns:
        Formatted string with macro indicator values and period changes
    """
    return route_to_vendor("get_forex_macro", pair, curr_date, look_back_days)
