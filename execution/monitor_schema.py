from __future__ import annotations
from typing import Literal
from pydantic import BaseModel


class MonitorDecision(BaseModel):
    action: Literal["HOLD", "EXIT"]
    reason: str
    confidence: float  # 0.0 – 1.0
