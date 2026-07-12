from __future__ import annotations

import re

from app.integrations.blockchain.models import WalletAsset, WalletSnapshot

CHAIN = "bnb"
MOCK_PROVIDER = "mock"
ADDRESS_PATTERN = re.compile(r"^0x[a-fA-F0-9]{40}$")


def validate_address(address: str) -> bool:
    return bool(ADDRESS_PATTERN.fullmatch(address))


async def get_wallet(address: str) -> WalletSnapshot:
    if not validate_address(address):
        raise ValueError("Invalid BNB Smart Chain wallet address")
    return WalletSnapshot(CHAIN, address, (WalletAsset("BNB", 2.5),), MOCK_PROVIDER)
