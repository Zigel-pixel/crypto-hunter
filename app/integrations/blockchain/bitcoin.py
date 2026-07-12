from __future__ import annotations

import re

from app.integrations.blockchain.models import WalletSnapshot

CHAIN = "bitcoin"
MOCK_PROVIDER = "mock"
ADDRESS_PATTERN = re.compile(
    r"^(?:[13][a-km-zA-HJ-NP-Z1-9]{25,34}|bc1[ac-hj-np-z02-9]{11,71})$"
)


def validate_address(address: str) -> bool:
    return bool(ADDRESS_PATTERN.fullmatch(address))


async def get_wallet(address: str) -> WalletSnapshot:
    if not validate_address(address):
        raise ValueError("Invalid Bitcoin wallet address")
    return WalletSnapshot(CHAIN, address, (), MOCK_PROVIDER)
