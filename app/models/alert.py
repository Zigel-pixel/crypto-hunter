from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Alert:
    id: int
    telegram_id: int
    coin: str
    condition: str
    target_price: float
