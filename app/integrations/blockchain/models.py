from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WalletAsset:
    symbol: str
    amount: float


@dataclass(frozen=True)
class WalletSnapshot:
    chain: str
    address: str
    assets: tuple[WalletAsset, ...]
    provider: str
