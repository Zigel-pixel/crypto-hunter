from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class LiveQuote:
    symbol: str
    price: float
    updated_at: datetime
    source: str

