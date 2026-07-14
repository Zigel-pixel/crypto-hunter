from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class WalletAsset:
    symbol: str
    amount: float
    usd_value: float | None = None
    standard: str | None = None


@dataclass(frozen=True)
class WalletSnapshot:
    chain: str
    address: str
    assets: tuple[WalletAsset, ...]
    provider: str
    total_usd_value: float | None = None
    updated_at: datetime | None = None
