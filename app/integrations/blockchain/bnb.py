from __future__ import annotations

import re
import os
import ssl
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

import aiohttp
import certifi

from app.integrations.blockchain.models import WalletAsset, WalletSnapshot

CHAIN = "bnb"
ADDRESS_PATTERN = re.compile(r"^0x[a-fA-F0-9]{40}$")
RPC_URL = os.getenv("BSC_RPC_URL", "").strip() or "https://bsc-rpc.publicnode.com"
REQUEST_TIMEOUT_SECONDS = 15
WEI_DECIMALS = 18


def validate_address(address: str) -> bool:
    return bool(ADDRESS_PATTERN.fullmatch(address))


async def get_wallet(address: str) -> WalletSnapshot:
    if not validate_address(address):
        raise ValueError("Invalid BNB Smart Chain wallet address")
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
            async with session.post(RPC_URL, json=payload, ssl=ssl_context) as response:
                response.raise_for_status()
                data: Any = await response.json()
    except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
        raise RuntimeError("BNB Chain balance provider is unavailable") from exc
    amount = _wei_to_bnb(data.get("result") if isinstance(data, dict) else None)
    if amount is None or (isinstance(data, dict) and data.get("error")):
        raise RuntimeError("BNB Chain balance provider returned invalid data")
    assets = () if amount == 0 else (WalletAsset(symbol="BNB", amount=amount),)
    return WalletSnapshot(
        chain=CHAIN,
        address=address,
        assets=assets,
        provider="publicnode",
        updated_at=datetime.now(timezone.utc),
    )


def _wei_to_bnb(value: Any) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        return float(Decimal(int(value, 16)) / (Decimal(10) ** WEI_DECIMALS))
    except (InvalidOperation, ValueError):
        return None
