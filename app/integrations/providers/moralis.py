"""Moralis Ethereum portfolio provider."""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
from decimal import Decimal, InvalidOperation
from typing import Any

import aiohttp

from app.integrations.blockchain.models import WalletAsset, WalletSnapshot
from app.integrations.providers import ProviderError, ProviderNotConfigured

CHAIN = "ethereum"
PROVIDER = "moralis"
API_KEY_ENV = "MORALIS_API_KEY"
NATIVE_BALANCE_URL = "https://deep-index.moralis.io/api/v2.2/{address}/balance"
WALLET_TOKENS_URL = "https://api.moralis.com/v1/wallets/{address}/tokens"
WEI_DECIMALS = 18
REQUEST_TIMEOUT_SECONDS = 20

logger = logging.getLogger(__name__)


async def get_wallet(address: str) -> WalletSnapshot:
    """Return real native ETH and ERC-20 balances from Moralis."""
    logger.info("Loading Moralis API key...")
    api_key = os.getenv(API_KEY_ENV, "").strip()
    if not api_key:
        logger.error("Moralis API key is missing.")
        raise ProviderNotConfigured("Moralis API key is missing.")
    logger.info("Moralis API key loaded.")

    headers = {"X-API-Key": api_key}
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
    native_url = NATIVE_BALANCE_URL.format(address=address)
    tokens_url = WALLET_TOKENS_URL.format(address=address)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            native_data, tokens_data = await asyncio.gather(
                _get_json(session, native_url, headers, {"chain": "eth"}),
                _get_json(
                    session,
                    tokens_url,
                    headers,
                    {"chains": "0x1"},
                ),
            )
    except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
        logger.exception("Moralis request raised an exception")
        raise ProviderError("Moralis request failed") from exc

    if not isinstance(native_data, dict):
        raise ProviderError("Moralis returned an invalid native balance")
    native_amount = _to_amount(native_data.get("balance"), WEI_DECIMALS)
    if native_amount is None:
        raise ProviderError("Moralis returned an invalid native balance")

    token_items = tokens_data.get("result", []) if isinstance(tokens_data, dict) else []
    if not isinstance(token_items, list):
        raise ProviderError("Moralis returned invalid token balances")

    native_usd_value = _native_usd_value(token_items)
    assets = [
        WalletAsset(
            symbol="ETH", amount=native_amount, usd_value=native_usd_value
        )
    ]
    for item in token_items:
        asset = _parse_asset(item)
        if asset is not None:
            assets.append(asset)

    nonzero_assets = tuple(asset for asset in assets if asset.amount != 0)
    return WalletSnapshot(
        chain=CHAIN,
        address=address,
        assets=nonzero_assets,
        provider=PROVIDER,
        total_usd_value=_total_usd_value(nonzero_assets),
    )


async def _get_json(
    session: aiohttp.ClientSession,
    url: str,
    headers: dict[str, str],
    params: dict[str, str],
) -> dict[str, Any] | list[Any]:
    logger.info("Calling Moralis...")
    async with session.get(url, headers=headers, params=params) as response:
        response_body = await response.text()
        logger.info("Moralis HTTP Status: %d", response.status)
        logger.info("Moralis Response: %s", response_body)
        if response.status == 401:
            logger.error("Moralis authentication failed.")
            raise ProviderError("Moralis authentication failed.")
        if response.status >= 400:
            raise ProviderError(f"Moralis returned HTTP {response.status}")
    try:
        data = json.loads(response_body)
    except json.JSONDecodeError as exc:
        raise ProviderError("Moralis returned invalid JSON") from exc
    if not isinstance(data, (dict, list)):
        raise ProviderError("Moralis returned an invalid response")
    return data


def _parse_asset(item: Any) -> WalletAsset | None:
    if not isinstance(item, dict) or item.get("nativeToken") is True:
        return None
    symbol = item.get("symbol")
    amount = _to_amount(
        item.get("balanceRaw", item.get("balance")), item.get("decimals")
    )
    usd_value = _to_float(item.get("usdValue"))
    if amount is None or amount == 0 or not isinstance(symbol, str) or not symbol:
        return None
    return WalletAsset(symbol=symbol, amount=amount, usd_value=usd_value)


def _native_usd_value(tokens: list[Any]) -> float | None:
    for item in tokens:
        if isinstance(item, dict) and item.get("nativeToken") is True:
            return _to_float(item.get("usdValue"))
    return None


def _to_amount(value: Any, decimals: Any) -> float | None:
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        return None
    if not isinstance(decimals, int) or decimals < 0:
        return None
    try:
        return float(Decimal(int(str(value))) / (Decimal(10) ** decimals))
    except (InvalidOperation, ValueError):
        return None


def _to_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if not isinstance(value, (str, int, float)):
        return None
    try:
        converted = float(value)
    except ValueError:
        return None
    return converted if math.isfinite(converted) else None


def _total_usd_value(assets: tuple[WalletAsset, ...]) -> float | None:
    if not assets or any(asset.usd_value is None for asset in assets):
        return None
    return sum(asset.usd_value for asset in assets if asset.usd_value is not None)
