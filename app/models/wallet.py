from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StoredWallet:
    network: str
    address: str


@dataclass(frozen=True)
class WalletProfile:
    id: int
    address: str
    address_family: str
    label: str | None
    networks: tuple[str, ...]
    last_refresh_at: str | None
    last_success_at: str | None = None
    native_balance: str | None = None
    usdt_balance: str | None = None
    native_symbol: str | None = None
    balance_status: str = "unknown"
    error_code: str | None = None
