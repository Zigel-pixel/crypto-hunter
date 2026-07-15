from __future__ import annotations

import asyncio
import logging
import os
import ssl
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import aiohttp
import certifi

from app.integrations.blockchain.models import WalletAsset, WalletSnapshot
from app.integrations.blockchain.errors import ProviderErrorCode, WalletProviderError

CHAIN = "tron"
DEFAULT_API_URL = "https://api.trongrid.io"
USDT_CONTRACT = "TXLAQ63Xg1NAzckPwKHvzw7CSEmLMEqcdj"
SUN_PER_TRX = 1_000_000
REQUEST_TIMEOUT_SECONDS = 15
logger = logging.getLogger(__name__)


def validate_address(address: str) -> bool:
    from app.models.wallet_address import AddressFamily
    from app.services.wallet_address_service import detect_wallet_address

    detected = detect_wallet_address(address)
    return bool(detected and detected.family is AddressFamily.TRON)


async def get_wallet(address: str) -> WalletSnapshot:
    if not validate_address(address):
        raise ValueError("Invalid Tron wallet address")
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            headers = {}
            if api_key := (os.getenv("TRONGRID_API_KEY") or os.getenv("TRON_API_KEY", "")).strip():
                headers["TRON-PRO-API-KEY"] = api_key
            api_url = os.getenv("TRON_API_URL", DEFAULT_API_URL).rstrip("/")
            async with session.get(
                f"{api_url}/v1/accounts/{address}", ssl=ssl_context, headers=headers
            ) as response:
                response.raise_for_status()
                payload: Any = await response.json()
    except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
        if isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
            code = ProviderErrorCode.TIMEOUT
        elif isinstance(exc, aiohttp.ClientResponseError) and exc.status == 429:
            code = ProviderErrorCode.RATE_LIMITED
        elif isinstance(exc, ValueError):
            code = ProviderErrorCode.MALFORMED_RESPONSE
        else:
            code = ProviderErrorCode.PROVIDER_UNAVAILABLE
        raise WalletProviderError(code, "Tron balance provider is unavailable") from exc
    rows = payload.get("data") if isinstance(payload, dict) else None
    account = rows[0] if isinstance(rows, list) and rows else {}
    if not isinstance(account, dict):
        raise WalletProviderError(ProviderErrorCode.MALFORMED_RESPONSE)
    assets: list[WalletAsset] = []
    try:
        trx_amount = Decimal(int(account.get("balance", 0))) / Decimal(SUN_PER_TRX)
    except (TypeError, ValueError) as exc:
        raise WalletProviderError(ProviderErrorCode.MALFORMED_RESPONSE) from exc
    assets.append(WalletAsset("TRX", trx_amount))
    try:
        for balances in account.get("trc20", []):
            if isinstance(balances, dict) and USDT_CONTRACT in balances:
                amount = Decimal(int(balances[USDT_CONTRACT])) / Decimal(1_000_000)
                assets.append(WalletAsset("USDT", amount, standard="TRC-20"))
    except (TypeError, ValueError) as exc:
        logger.warning("TRON USDT balance was malformed: %s", exc)
    if not any(asset.symbol == "USDT" for asset in assets):
        assets.append(WalletAsset("USDT", Decimal(0), standard="TRC-20"))
    return WalletSnapshot(
        chain=CHAIN,
        address=address,
        assets=tuple(assets),
        provider="trongrid_public",
        updated_at=datetime.now(timezone.utc),
    )
