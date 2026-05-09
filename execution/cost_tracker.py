"""Estimate LLM API cost from token counts."""
from __future__ import annotations

# (input_usd, output_usd) per 1M tokens — approximate public pricing
_COST_PER_1M: dict[str, tuple[float, float]] = {
    "gpt-5.4-mini":  (0.15,   0.60),
    "gpt-5.4":       (2.50,  10.00),
    "gpt-4o-mini":   (0.15,   0.60),
    "gpt-4o":        (2.50,  10.00),
    "gemini-flash":  (0.075,  0.30),
    "gemini":        (0.10,   0.40),
    "claude-haiku":  (0.25,   1.25),
    "claude":        (3.00,  15.00),
    "deepseek":      (0.14,   0.28),
    "grok":          (2.00,   6.00),
    "gemma":         (0.07,   0.07),
    "llama":         (0.09,   0.09),
    "qwen":          (0.07,   0.21),
    "_default":      (1.00,   3.00),
}


def _lookup(model: str) -> tuple[float, float]:
    m = model.lower()
    for key, price in _COST_PER_1M.items():
        if key != "_default" and key in m:
            return price
    return _COST_PER_1M["_default"]


class CostTracker:
    def __init__(self, model: str):
        self._in_rate, self._out_rate = _lookup(model)

    def estimate_usd(self, tokens_in: int, tokens_out: int) -> float:
        return (tokens_in * self._in_rate + tokens_out * self._out_rate) / 1_000_000

    def summary(self, stats: dict) -> dict:
        usd = self.estimate_usd(stats.get("tokens_in", 0), stats.get("tokens_out", 0))
        return {**stats, "estimated_usd": round(usd, 4)}

    def exceeds(self, stats: dict, max_usd: float) -> bool:
        return self.estimate_usd(stats.get("tokens_in", 0), stats.get("tokens_out", 0)) > max_usd
