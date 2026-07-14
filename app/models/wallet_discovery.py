from __future__ import annotations

from dataclasses import dataclass

from app.integrations.blockchain.models import WalletSnapshot
from app.models.wallet_address import NormalizedWalletAddress


@dataclass(frozen=True)
class WalletDiscoveryResult:
    address: NormalizedWalletAddress
    scanned_networks: tuple[str, ...]
    active: tuple[WalletSnapshot, ...]
    warnings: tuple[str, ...] = ()
