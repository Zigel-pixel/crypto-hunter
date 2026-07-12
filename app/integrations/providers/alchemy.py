"""Alchemy Ethereum portfolio provider."""

from __future__ import annotations

import asyncio
import os
from decimal import Decimal, InvalidOperation
from typing import Any

import aiohttp

from app.integrations.blockchain.models import WalletAsset, WalletSnapshot
from app.integrations.providers import ProviderError, ProviderNotConfigured

CHAIN = "ethereum"
PROVIDER = "alchemy"
API_KEY_ENV = "ALCHEMY_API_KEY"
API_URL = "https://eth-mainnet.g.alchemy.com/v2/{api_key}"
WEI_DECIMALS = 18
REQUEST_TIMEOUT_SECONDS = 20
METADATA_CONCURRENCY = 10


async def get_wallet(address: str) -> WalletSnapshot:
    """Return real Ethereum balances from Alchemy JSON-RPC."""
    api_key = os.getenv(API_KEY_ENV, "").strip()
    if not api_key:
        raise ProviderNotConfigured("Alchemy API key is not configured")

    url = API_URL.format(api_key=api_key)
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            native_raw, token_data = await asyncio.gather(
                _rpc(session, url, "eth_getBalance", [address, "latest"]),
                _rpc(session, url, "alchemy_getTokenBalances", [address]),
            )
            token_assets = await _get_token_assets(session, url, token_data)
    except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
        raise ProviderError("Alchemy request failed") from exc

    native_amount = _to_amount(native_raw, WEI_DECIMALS, base=16)
    if native_amount is None:
        raise ProviderError("Alchemy returned an invalid native balance")

    assets = [WalletAsset(symbol="ETH", amount=native_amount), *token_assets]
    return WalletSnapshot(
        chain=CHAIN,
        address=address,
        assets=tuple(asset for asset in assets if asset.amount != 0),
        provider=PROVIDER,
        total_usd_value=None,
    )


async def _rpc(
    session: aiohttp.ClientSession, url: str, method: str, params: list[Any]
) -> Any:
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    async with session.post(url, json=payload) as response:
        if response.status >= 400:
            raise ProviderError(f"Alchemy returned HTTP {response.status}")
        data = await response.json()
    if not isinstance(data, dict) or "error" in data or "result" not in data:
        raise ProviderError("Alchemy returned an invalid response")
    return data["result"]


async def _get_token_assets(
    session: aiohttp.ClientSession, url: str, data: Any
) -> list[WalletAsset]:
    if not isinstance(data, dict) or not isinstance(data.get("tokenBalances"), list):
        raise ProviderError("Alchemy returned invalid token balances")
    semaphore = asyncio.Semaphore(METADATA_CONCURRENCY)

    async def get_asset(token: Any) -> WalletAsset | None:
        if not isinstance(token, dict):
            return None
        contract_address = token.get("contractAddress")
        raw_balance = token.get("tokenBalance")
        if not isinstance(contract_address, str) or not isinstance(raw_balance, str):
            return None
        if _to_amount(raw_balance, 0, base=16) in (None, 0):
            return None
        async with semaphore:
            metadata = await _rpc(
                session, url, "alchemy_getTokenMetadata", [contract_address]
            )
        if not isinstance(metadata, dict):
            return None
        amount = _to_amount(raw_balance, metadata.get("decimals"), base=16)
        if amount is None or amount == 0:
            return None
        symbol = metadata.get("symbol")
        return WalletAsset(
            symbol=symbol if isinstance(symbol, str) and symbol else contract_address,
            amount=amount,
        )

    assets = await asyncio.gather(
        *(get_asset(token) for token in data["tokenBalances"])
    )
    return [asset for asset in assets if asset is not None]


def _to_amount(value: Any, decimals: Any, base: int = 10) -> float | None:
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        return None
    if not isinstance(decimals, int) or decimals < 0:
        return None
    try:
        return float(Decimal(int(str(value), base)) / (Decimal(10) ** decimals))
    except (InvalidOperation, ValueError):
        return None
