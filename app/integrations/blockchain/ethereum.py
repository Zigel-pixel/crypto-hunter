"""Ethereum integration that selects a real portfolio-data provider."""

from __future__ import annotations

from app.integrations.blockchain.models import WalletSnapshot
from app.integrations.providers.manager import (
    ProviderManagerError,
    ethereum_provider_manager,
)

class EthereumWalletError(RuntimeError):
    """Raised after every configured Ethereum provider has failed."""


def validate_address(address: str) -> bool:
    """Return whether *address* has valid Ethereum address syntax."""
    from app.models.wallet_address import AddressFamily
    from app.services.wallet_address_service import detect_wallet_address

    detected = detect_wallet_address(address)
    return bool(detected and detected.family is AddressFamily.EVM)


async def get_wallet(address: str) -> WalletSnapshot:
    """Fetch a real Ethereum portfolio using configured provider priority."""
    if not validate_address(address):
        raise ValueError("Invalid Ethereum wallet address")

    try:
        return await ethereum_provider_manager.get_wallet(address)
    except ProviderManagerError as exc:
        raise EthereumWalletError(str(exc)) from exc
