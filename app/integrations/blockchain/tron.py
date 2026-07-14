from __future__ import annotations

import logging
import os
import ssl
from datetime import datetime, timezone
from typing import Any

import aiohttp
import certifi

from app.integrations.blockchain.models import WalletAsset, WalletSnapshot

CHAIN = "tron"
API_URL = "https://api.trongrid.io/v1/accounts/{address}"
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
            if api_key := os.getenv("TRON_API_KEY", "").strip():
                headers["TRON-PRO-API-KEY"] = api_key
            async with session.get(
                API_URL.format(address=address), ssl=ssl_context, headers=headers
            ) as response:
                response.raise_for_status()
                payload: Any = await response.json()
    except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
        raise RuntimeError("Tron balance provider is unavailable") from exc
    rows = payload.get("data") if isinstance(payload, dict) else None
    account = rows[0] if isinstance(rows, list) and rows else {}
    if not isinstance(account, dict):
        raise RuntimeError("Tron balance provider returned invalid data")
    assets: list[WalletAsset] = []
    try:
        trx_amount = int(account.get("balance", 0)) / SUN_PER_TRX
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Tron provider returned an invalid TRX balance") from exc
    if trx_amount:
        assets.append(WalletAsset("TRX", trx_amount))
    try:
        for balances in account.get("trc20", []):
            if isinstance(balances, dict) and USDT_CONTRACT in balances:
                amount = int(balances[USDT_CONTRACT]) / 1_000_000
                if amount:
                    assets.append(WalletAsset("USDT", amount, standard="TRC-20"))
    except (TypeError, ValueError) as exc:
        logger.warning("TRON USDT balance was malformed: %s", exc)
    return WalletSnapshot(
        chain=CHAIN,
        address=address,
        assets=tuple(assets),
        provider="trongrid_public",
        updated_at=datetime.now(timezone.utc),
    )
