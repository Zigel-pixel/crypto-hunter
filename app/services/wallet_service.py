"""Wallet business logic independent of blockchain API providers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.integrations.blockchain import bnb, bitcoin, ethereum, solana
from app.integrations.blockchain.models import WalletSnapshot

WalletFetcher = Callable[[str], Awaitable[WalletSnapshot]]
AddressValidator = Callable[[str], bool]

_WALLET_FETCHERS: dict[str, WalletFetcher] = {
    "bitcoin": bitcoin.get_wallet,
    "ethereum": ethereum.get_wallet,
    "solana": solana.get_wallet,
    "bnb": bnb.get_wallet,
}
_ADDRESS_VALIDATORS: dict[str, AddressValidator] = {
    "bitcoin": bitcoin.validate_address,
    "ethereum": ethereum.validate_address,
    "solana": solana.validate_address,
    "bnb": bnb.validate_address,
}


def supported_chains() -> tuple[str, ...]:
    return tuple(_WALLET_FETCHERS)


def validate_wallet_address(chain: str, address: str) -> bool:
    validator = _ADDRESS_VALIDATORS.get(chain.lower())
    return bool(validator and validator(address))


async def get_wallet(chain: str, address: str) -> WalletSnapshot:
    normalized_chain = chain.lower()
    fetcher = _WALLET_FETCHERS.get(normalized_chain)
    if fetcher is None:
        raise ValueError(f"Unsupported blockchain: {chain}")
    if not validate_wallet_address(normalized_chain, address):
        raise ValueError(f"Invalid {normalized_chain} wallet address")
    return await fetcher(address)
