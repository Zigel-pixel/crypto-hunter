"""Keyless public Ethereum JSON-RPC fallback provider."""

from __future__ import annotations

import json
import logging
import ssl
from decimal import Decimal, InvalidOperation
from typing import Any

import aiohttp
import certifi

from app.integrations.blockchain.models import WalletAsset, WalletSnapshot
from app.integrations.providers import ProviderError

CHAIN = "ethereum"
PROVIDER = "public_rpc"
API_URL = "https://ethereum-rpc.publicnode.com"
WEI_DECIMALS = 18
REQUEST_TIMEOUT_SECONDS = 20

logger = logging.getLogger(__name__)


async def get_wallet(address: str) -> WalletSnapshot:
    """Return a real native ETH balance using a public read-only RPC endpoint."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_getBalance",
        "params": [address, "latest"],
    }
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            result = await _call_rpc(session, payload, ssl_context)
    except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
        logger.exception("Public Ethereum RPC request raised an exception")
        raise ProviderError("Public Ethereum RPC request failed") from exc

    native_amount = _to_amount(result)
    if native_amount is None:
        raise ProviderError("Public Ethereum RPC returned an invalid native balance")

    assets = (WalletAsset(symbol="ETH", amount=native_amount),)
    return WalletSnapshot(
        chain=CHAIN,
        address=address,
        assets=tuple(asset for asset in assets if asset.amount != 0),
        provider=PROVIDER,
        total_usd_value=None,
    )


async def _call_rpc(
    session: aiohttp.ClientSession,
    payload: dict[str, Any],
    ssl_context: ssl.SSLContext,
) -> Any:
    logger.info("Calling Public Ethereum RPC...")
    async with session.post(API_URL, json=payload, ssl=ssl_context) as response:
        response_body = await response.text()
        logger.info("Public Ethereum RPC HTTP Status: %d", response.status)
        logger.info("Public Ethereum RPC Response: %s", response_body)
        if response.status >= 400:
            raise ProviderError(
                f"Public Ethereum RPC returned HTTP {response.status}"
            )
    try:
        data = json.loads(response_body)
    except json.JSONDecodeError as exc:
        raise ProviderError("Public Ethereum RPC returned invalid JSON") from exc
    if not isinstance(data, dict) or "error" in data or "result" not in data:
        raise ProviderError("Public Ethereum RPC returned an invalid response")
    return data["result"]


def _to_amount(value: Any) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        return float(Decimal(int(value, 16)) / (Decimal(10) ** WEI_DECIMALS))
    except (InvalidOperation, ValueError):
        return None
