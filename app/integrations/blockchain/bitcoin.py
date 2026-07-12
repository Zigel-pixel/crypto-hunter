from __future__ import annotations

import re
import ssl
from datetime import datetime, timezone
from typing import Any

import aiohttp
import certifi

from app.integrations.blockchain.models import WalletAsset, WalletSnapshot

CHAIN = "bitcoin"
ADDRESS_PATTERN = re.compile(
    r"^(?:[13][a-km-zA-HJ-NP-Z1-9]{25,34}|bc1[ac-hj-np-z02-9]{11,71})$"
)
API_URL = "https://blockstream.info/api/address/{address}"
REQUEST_TIMEOUT_SECONDS = 15
SATOSHIS_PER_BTC = 100_000_000


def validate_address(address: str) -> bool:
    return bool(ADDRESS_PATTERN.fullmatch(address))


async def get_wallet(address: str) -> WalletSnapshot:
    if not validate_address(address):
        raise ValueError("Invalid Bitcoin wallet address")
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                API_URL.format(address=address), ssl=ssl_context
            ) as response:
                response.raise_for_status()
                data: Any = await response.json()
    except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
        raise RuntimeError("Bitcoin balance provider is unavailable") from exc

    if not isinstance(data, dict):
        raise RuntimeError("Bitcoin balance provider returned invalid data")
    confirmed = _balance_from_stats(data.get("chain_stats"))
    mempool = _balance_from_stats(data.get("mempool_stats"))
    if confirmed is None or mempool is None:
        raise RuntimeError("Bitcoin balance provider returned invalid data")
    amount = (confirmed + mempool) / SATOSHIS_PER_BTC
    assets = () if amount == 0 else (WalletAsset(symbol="BTC", amount=amount),)
    return WalletSnapshot(
        chain=CHAIN,
        address=address,
        assets=assets,
        provider="blockstream",
        updated_at=datetime.now(timezone.utc),
    )


def _balance_from_stats(value: Any) -> int | None:
    if not isinstance(value, dict):
        return None
    funded = value.get("funded_txo_sum")
    spent = value.get("spent_txo_sum")
    if not isinstance(funded, int) or not isinstance(spent, int):
        return None
    return funded - spent
