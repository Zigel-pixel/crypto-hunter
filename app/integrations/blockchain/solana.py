from __future__ import annotations

import re
import ssl
from datetime import datetime, timezone
from typing import Any

import aiohttp
import certifi

from app.integrations.blockchain.models import WalletAsset, WalletSnapshot

CHAIN = "solana"
ADDRESS_PATTERN = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")
RPC_URL = "https://solana-rpc.publicnode.com"
REQUEST_TIMEOUT_SECONDS = 15
LAMPORTS_PER_SOL = 1_000_000_000


def validate_address(address: str) -> bool:
    return bool(ADDRESS_PATTERN.fullmatch(address))


async def get_wallet(address: str) -> WalletSnapshot:
    if not validate_address(address):
        raise ValueError("Invalid Solana wallet address")
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getBalance",
        "params": [address, {"commitment": "confirmed"}],
    }
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(RPC_URL, json=payload, ssl=ssl_context) as response:
                response.raise_for_status()
                data: Any = await response.json()
    except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
        raise RuntimeError("Solana balance provider is unavailable") from exc
    result = data.get("result") if isinstance(data, dict) else None
    lamports = result.get("value") if isinstance(result, dict) else None
    if not isinstance(lamports, int) or (isinstance(data, dict) and data.get("error")):
        raise RuntimeError("Solana balance provider returned invalid data")
    amount = lamports / LAMPORTS_PER_SOL
    assets = () if amount == 0 else (WalletAsset(symbol="SOL", amount=amount),)
    return WalletSnapshot(
        chain=CHAIN,
        address=address,
        assets=assets,
        provider="publicnode",
        updated_at=datetime.now(timezone.utc),
    )
