from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StoredWallet:
    network: str
    address: str
