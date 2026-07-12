"""Ethereum integration that selects a real portfolio-data provider."""

from __future__ import annotations

import logging
import re

from app.integrations.blockchain.models import WalletSnapshot
from app.integrations.providers import ProviderError, ProviderNotConfigured
from app.integrations.providers import alchemy, moralis

ADDRESS_PATTERN = re.compile(r"^0x[a-fA-F0-9]{40}$")

logger = logging.getLogger(__name__)

_PROVIDERS = (moralis, alchemy)


class EthereumWalletError(RuntimeError):
    """Raised after every configured Ethereum provider has failed."""


def validate_address(address: str) -> bool:
    """Return whether *address* has valid Ethereum address syntax."""
    return bool(ADDRESS_PATTERN.fullmatch(address))


async def get_wallet(address: str) -> WalletSnapshot:
    """Fetch a real Ethereum portfolio using configured provider priority."""
    if not validate_address(address):
        raise ValueError("Invalid Ethereum wallet address")

    failures: list[str] = []
    for provider in _PROVIDERS:
        try:
            return await provider.get_wallet(address)
        except ProviderNotConfigured:
            continue
        except ProviderError as exc:
            failures.append(provider.PROVIDER)
            logger.warning("Ethereum provider %s failed: %s", provider.PROVIDER, exc)
        except Exception:
            failures.append(provider.PROVIDER)
            logger.exception("Ethereum provider %s failed unexpectedly", provider.PROVIDER)

    if not failures:
        raise EthereumWalletError(
            "Ethereum wallet providers are not configured. "
            "Set MORALIS_API_KEY or ALCHEMY_API_KEY."
        )
    raise EthereumWalletError("Unable to load the Ethereum wallet portfolio.")
