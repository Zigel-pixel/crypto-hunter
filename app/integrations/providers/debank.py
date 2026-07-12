"""DeBank Ethereum portfolio provider."""

from __future__ import annotations

import math
import os
from typing import Any

import aiohttp

from app.integrations.blockchain.models import WalletAsset, WalletSnapshot
from app.integrations.providers import ProviderError, ProviderNotConfigured

CHAIN = "ethereum"
PROVIDER = "debank"
API_KEY_ENV = "DEBANK_API_KEY"
API_URL = "https://pro-openapi.debank.com/v1/user/token_list"
REQUEST_TIMEOUT_SECONDS = 20


async def get_wallet(address: str) -> WalletSnapshot:
    """Return the real Ethereum token portfolio reported by DeBank."""
    api_key = os.getenv(API_KEY_ENV, "").strip()
    if not api_key:
        raise ProviderNotConfigured("DeBank API key is not configured")

    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
    headers = {"Accept": "application/json", "AccessKey": api_key}
    params = {"id": address, "chain_id": "eth", "is_all": "true"}
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(API_URL, headers=headers, params=params) as response:
                if response.status >= 400:
                    raise ProviderError(f"DeBank returned HTTP {response.status}")
                data = await response.json()
    except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
        raise ProviderError("DeBank request failed") from exc

    if not isinstance(data, list):
        raise ProviderError("DeBank returned an invalid portfolio")

    assets = tuple(asset for item in data if (asset := _parse_asset(item)) is not None)
    return WalletSnapshot(
        chain=CHAIN,
        address=address,
        assets=assets,
        provider=PROVIDER,
        total_usd_value=_total_usd_value(assets),
    )


def _parse_asset(item: Any) -> WalletAsset | None:
    if not isinstance(item, dict):
        return None
    amount = _to_float(item.get("amount"))
    symbol = item.get("optimized_symbol") or item.get("display_symbol") or item.get(
        "symbol"
    )
    if amount is None or amount == 0 or not isinstance(symbol, str) or not symbol:
        return None

    price = _to_float(item.get("price"))
    usd_value = amount * price if price is not None and price > 0 else None
    return WalletAsset(symbol=symbol, amount=amount, usd_value=usd_value)


def _total_usd_value(assets: tuple[WalletAsset, ...]) -> float | None:
    if not assets or any(asset.usd_value is None for asset in assets):
        return None
    return sum(asset.usd_value for asset in assets if asset.usd_value is not None)


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
