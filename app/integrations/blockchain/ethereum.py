from __future__ import annotations

import re

from app.integrations.blockchain.models import WalletAsset, WalletSnapshot

CHAIN = "ethereum"
MOCK_PROVIDER = "mock"
ADDRESS_PATTERN = re.compile(r"^0x[a-fA-F0-9]{40}$")


def validate_address(address: str) -> bool:
    return bool(ADDRESS_PATTERN.fullmatch(address))


async def get_wallet(address: str) -> WalletSnapshot:
    if not validate_address(address):
        raise ValueError("Invalid Ethereum wallet address")
    return WalletSnapshot(CHAIN, address, (WalletAsset("ETH", 1.25),), MOCK_PROVIDER)
