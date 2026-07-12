"""Asynchronous Ethereum mainnet wallet integration.

Moralis is the primary provider. Alchemy is used when Moralis is unavailable or
its API key is not configured. API keys are read from the environment at request
time so deployments can rotate them without source-code changes.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from decimal import Decimal, InvalidOperation
from typing import Any

import aiohttp

from app.integrations.blockchain.models import WalletAsset, WalletSnapshot

CHAIN = "ethereum"
NATIVE_SYMBOL = "ETH"
MORALIS_PROVIDER = "moralis"
ALCHEMY_PROVIDER = "alchemy"

MORALIS_API_KEY_ENV = "MORALIS_API_KEY"
ALCHEMY_API_KEY_ENV = "ALCHEMY_API_KEY"
MORALIS_BASE_URL = "https://deep-index.moralis.io/api/v2.2"
MORALIS_WALLET_TOKENS_URL = "https://api.moralis.com/v1/wallets/{address}/tokens"
ALCHEMY_ETHEREUM_URL = "https://eth-mainnet.g.alchemy.com/v2/{api_key}"
MORALIS_CHAIN = "eth"
WEI_DECIMALS = 18
REQUEST_TIMEOUT_SECONDS = 20
TOKEN_METADATA_CONCURRENCY = 10

ADDRESS_PATTERN = re.compile(r"^0x[a-fA-F0-9]{40}$")

logger = logging.getLogger(__name__)


class EthereumWalletError(RuntimeError):
    """Raised when Ethereum wallet data cannot be retrieved from a provider."""


def validate_address(address: str) -> bool:
    """Return whether *address* is a syntactically valid EVM address."""
    return bool(ADDRESS_PATTERN.fullmatch(address))


async def get_wallet(address: str) -> WalletSnapshot:
    """Return Ethereum native and ERC-20 balances for a wallet address.

    Raises:
        ValueError: The supplied address is malformed.
        EthereumWalletError: No provider is configured or all providers failed.
    """
    if not validate_address(address):
        raise ValueError("Invalid Ethereum wallet address")

    moralis_api_key = os.getenv(MORALIS_API_KEY_ENV, "").strip()
    alchemy_api_key = os.getenv(ALCHEMY_API_KEY_ENV, "").strip()

    if moralis_api_key:
        try:
            return await _get_wallet_from_moralis(address, moralis_api_key)
        except EthereumWalletError as exc:
            logger.warning("Moralis Ethereum wallet request failed: %s", exc)

    if alchemy_api_key:
        try:
            return await _get_wallet_from_alchemy(address, alchemy_api_key)
        except EthereumWalletError as exc:
            logger.warning("Alchemy Ethereum wallet request failed: %s", exc)

    if not moralis_api_key and not alchemy_api_key:
        raise EthereumWalletError(
            "Ethereum wallet provider is not configured. "
            "Set MORALIS_API_KEY or ALCHEMY_API_KEY."
        )

    raise EthereumWalletError("Unable to retrieve Ethereum wallet balances.")


async def _get_wallet_from_moralis(address: str, api_key: str) -> WalletSnapshot:
    headers = {"X-API-Key": api_key}
    native_url = f"{MORALIS_BASE_URL}/{address}/balance"
    tokens_url = MORALIS_WALLET_TOKENS_URL.format(address=address)

    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            native_data, token_data = await asyncio.gather(
                _get_json(
                    session,
                    native_url,
                    headers=headers,
                    params={"chain": MORALIS_CHAIN},
                ),
                _get_json(
                    session,
                    tokens_url,
                    headers=headers,
                    params={"chains": "0x1", "excludeSpam": "true"},
                ),
            )
    except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
        raise EthereumWalletError("Moralis request failed") from exc

    if not isinstance(native_data, dict):
        raise EthereumWalletError("Moralis returned an invalid native balance")
    native_balance = _to_token_amount(native_data.get("balance"), WEI_DECIMALS)
    if native_balance is None:
        raise EthereumWalletError("Moralis returned an invalid native balance")

    assets = [WalletAsset(NATIVE_SYMBOL, native_balance)]
    assets.extend(_parse_moralis_tokens(token_data))
    return WalletSnapshot(CHAIN, address, tuple(assets), MORALIS_PROVIDER)


async def _get_wallet_from_alchemy(address: str, api_key: str) -> WalletSnapshot:
    url = ALCHEMY_ETHEREUM_URL.format(api_key=api_key)
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            native_result, tokens_result = await asyncio.gather(
                _alchemy_rpc(session, url, "eth_getBalance", [address, "latest"]),
                _alchemy_rpc(session, url, "alchemy_getTokenBalances", [address]),
            )
            token_assets = await _get_alchemy_token_assets(session, url, tokens_result)
    except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
        raise EthereumWalletError("Alchemy request failed") from exc

    native_balance = _to_token_amount(native_result, WEI_DECIMALS, base=16)
    if native_balance is None:
        raise EthereumWalletError("Alchemy returned an invalid native balance")

    return WalletSnapshot(
        CHAIN,
        address,
        tuple([WalletAsset(NATIVE_SYMBOL, native_balance), *token_assets]),
        ALCHEMY_PROVIDER,
    )


async def _get_json(
    session: aiohttp.ClientSession,
    url: str,
    *,
    headers: dict[str, str],
    params: dict[str, str],
) -> dict[str, Any] | list[dict[str, Any]]:
    async with session.get(url, headers=headers, params=params) as response:
        if response.status >= 400:
            raise EthereumWalletError(f"Provider returned HTTP {response.status}")
        data = await response.json()
    if not isinstance(data, (dict, list)):
        raise EthereumWalletError("Provider returned an invalid response")
    return data


async def _alchemy_rpc(
    session: aiohttp.ClientSession,
    url: str,
    method: str,
    params: list[Any],
) -> Any:
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    async with session.post(url, json=payload) as response:
        if response.status >= 400:
            raise EthereumWalletError(f"Provider returned HTTP {response.status}")
        data = await response.json()

    if not isinstance(data, dict):
        raise EthereumWalletError("Provider returned an invalid response")
    if "error" in data:
        raise EthereumWalletError("Provider rejected the wallet request")
    if "result" not in data:
        raise EthereumWalletError("Provider returned no result")
    return data["result"]


def _parse_moralis_tokens(data: dict[str, Any] | list[dict[str, Any]]) -> list[WalletAsset]:
    tokens = data.get("result", []) if isinstance(data, dict) else data
    if not isinstance(tokens, list):
        raise EthereumWalletError("Moralis returned invalid token balances")

    assets: list[WalletAsset] = []
    for token in tokens:
        if not isinstance(token, dict) or _is_spam_token(token):
            continue
        amount = _to_token_amount(
            token.get("balanceRaw", token.get("balance")), token.get("decimals")
        )
        symbol = token.get("symbol")
        if amount is None or amount == 0 or not isinstance(symbol, str) or not symbol:
            continue
        assets.append(WalletAsset(symbol, amount))
    return assets


async def _get_alchemy_token_assets(
    session: aiohttp.ClientSession, url: str, data: Any
) -> list[WalletAsset]:
    if not isinstance(data, dict):
        raise EthereumWalletError("Alchemy returned invalid token balances")
    balances = data.get("tokenBalances", [])
    if not isinstance(balances, list):
        raise EthereumWalletError("Alchemy returned invalid token balances")

    semaphore = asyncio.Semaphore(TOKEN_METADATA_CONCURRENCY)

    async def get_asset(token: Any) -> WalletAsset | None:
        if not isinstance(token, dict):
            return None
        contract_address = token.get("contractAddress")
        raw_balance = token.get("tokenBalance")
        if not isinstance(contract_address, str) or not isinstance(raw_balance, str):
            return None
        if _to_token_amount(raw_balance, 0, base=16) in (None, 0):
            return None

        async with semaphore:
            metadata = await _alchemy_rpc(
                session, url, "alchemy_getTokenMetadata", [contract_address]
            )
        if not isinstance(metadata, dict):
            return None
        amount = _to_token_amount(raw_balance, metadata.get("decimals"), base=16)
        symbol = metadata.get("symbol")
        if amount is None or amount == 0:
            return None
        return WalletAsset(
            symbol if isinstance(symbol, str) and symbol else contract_address,
            amount,
        )

    results = await asyncio.gather(*(get_asset(token) for token in balances))
    return [asset for asset in results if asset is not None]


def _is_spam_token(token: dict[str, Any]) -> bool:
    value = token.get("possible_spam", token.get("possibleSpam", False))
    return value is True or value == "true"


def _to_token_amount(value: Any, decimals: Any, base: int = 10) -> float | None:
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        return None
    if not isinstance(decimals, int) or decimals < 0:
        return None
    try:
        raw_amount = Decimal(int(str(value), base))
        return float(raw_amount / (Decimal(10) ** decimals))
    except (InvalidOperation, ValueError):
        return None
