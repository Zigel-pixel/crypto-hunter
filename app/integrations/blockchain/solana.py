from __future__ import annotations

import re

from app.integrations.blockchain.models import WalletSnapshot

CHAIN = "solana"
MOCK_PROVIDER = "mock"
ADDRESS_PATTERN = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")


def validate_address(address: str) -> bool:
    return bool(ADDRESS_PATTERN.fullmatch(address))


async def get_wallet(address: str) -> WalletSnapshot:
    if not validate_address(address):
        raise ValueError("Invalid Solana wallet address")
    return WalletSnapshot(CHAIN, address, (), MOCK_PROVIDER)
