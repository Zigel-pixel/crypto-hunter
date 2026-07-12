from __future__ import annotations

import re
import ssl
from datetime import datetime, timezone
from typing import Any

import aiohttp
import certifi

from app.integrations.blockchain.models import WalletAsset, WalletSnapshot

CHAIN = "tron"
ADDRESS_PATTERN = re.compile(r"^T[1-9A-HJ-NP-Za-km-z]{33}$")
API_URL = "https://api.trongrid.io/v1/accounts/{address}"
USDT_CONTRACT = "TXLAQ63Xg1NAzckPwKHvzw7CSEmLMEqcdj"
SUN_PER_TRX = 1_000_000
REQUEST_TIMEOUT_SECONDS = 15


def validate_address(address: str) -> bool:
    return bool(ADDRESS_PATTERN.fullmatch(address))


async def get_wallet(address: str) -> WalletSnapshot:
    if not validate_address(address):
        raise ValueError("Invalid Tron wallet address")
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                API_URL.format(address=address), ssl=ssl_context
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
    trx_amount = float(account.get("balance", 0)) / SUN_PER_TRX
    if trx_amount:
        assets.append(WalletAsset("TRX", trx_amount))
    for balances in account.get("trc20", []):
        if isinstance(balances, dict) and USDT_CONTRACT in balances:
            assets.append(WalletAsset("USDT", int(balances[USDT_CONTRACT]) / 1_000_000))
    return WalletSnapshot(
        chain=CHAIN,
        address=address,
        assets=tuple(assets),
        provider="trongrid_public",
        updated_at=datetime.now(timezone.utc),
    )
