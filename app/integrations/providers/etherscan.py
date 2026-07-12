"""Etherscan Ethereum native-balance fallback provider."""

from __future__ import annotations

import json
import logging
import os
import ssl
from decimal import Decimal, InvalidOperation
from typing import Any

import aiohttp
import certifi

from app.integrations.blockchain.models import WalletAsset, WalletSnapshot
from app.integrations.providers import ProviderError, ProviderNotConfigured

CHAIN = "ethereum"
PROVIDER = "etherscan"
API_KEY_ENV = "ETHERSCAN_API_KEY"
API_URL = "https://api.etherscan.io/v2/api"
WEI_DECIMALS = 18
REQUEST_TIMEOUT_SECONDS = 20

logger = logging.getLogger(__name__)


async def get_wallet(address: str) -> WalletSnapshot:
    """Return a real Ethereum native balance from Etherscan's public API tier."""
    logger.info("Loading Etherscan API key...")
    api_key = os.getenv(API_KEY_ENV, "").strip()
    if not api_key:
        logger.error("Etherscan API key is missing.")
        raise ProviderNotConfigured("Etherscan API key is missing.")
    logger.info("Etherscan API key loaded.")

    params = {
        "chainid": "1",
        "module": "account",
        "action": "balance",
        "address": address,
        "tag": "latest",
        "apikey": api_key,
    }
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            data = await _get_json(session, params, ssl_context)
    except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
        logger.exception("Etherscan request raised an exception")
        raise ProviderError("Etherscan request failed") from exc

    if not isinstance(data, dict):
        raise ProviderError("Etherscan returned an invalid response")
    if data.get("status") != "1":
        message = str(data.get("result") or data.get("message") or "Unknown error")
        if "invalid api key" in message.lower():
            logger.error("Etherscan authentication failed.")
            raise ProviderError("Etherscan authentication failed.")
        raise ProviderError(f"Etherscan request failed: {message}")

    native_amount = _to_amount(data.get("result"))
    if native_amount is None:
        raise ProviderError("Etherscan returned an invalid native balance")

    assets = (WalletAsset(symbol="ETH", amount=native_amount),)
    return WalletSnapshot(
        chain=CHAIN,
        address=address,
        assets=tuple(asset for asset in assets if asset.amount != 0),
        provider=PROVIDER,
        total_usd_value=None,
    )


async def _get_json(
    session: aiohttp.ClientSession,
    params: dict[str, str],
    ssl_context: ssl.SSLContext,
) -> dict[str, Any] | list[Any]:
    logger.info("Calling Etherscan...")
    async with session.get(API_URL, params=params, ssl=ssl_context) as response:
        response_body = await response.text()
        logger.info("Etherscan HTTP Status: %d", response.status)
        logger.info("Etherscan Response: %s", response_body)
        if response.status == 401:
            logger.error("Etherscan authentication failed.")
            raise ProviderError("Etherscan authentication failed.")
        if response.status >= 400:
            raise ProviderError(f"Etherscan returned HTTP {response.status}")
    try:
        data = json.loads(response_body)
    except json.JSONDecodeError as exc:
        raise ProviderError("Etherscan returned invalid JSON") from exc
    if not isinstance(data, (dict, list)):
        raise ProviderError("Etherscan returned an invalid response")
    return data


def _to_amount(value: Any) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        return float(Decimal(int(value)) / (Decimal(10) ** WEI_DECIMALS))
    except (InvalidOperation, ValueError):
        return None
