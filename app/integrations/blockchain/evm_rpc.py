from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import aiohttp

from app.integrations.blockchain.models import WalletAsset, WalletSnapshot
from app.integrations.blockchain.network_registry import EvmNetwork


class EvmRpcError(RuntimeError):
    pass


async def get_wallet(network: EvmNetwork, address: str, timeout_seconds: int) -> WalletSnapshot:
    if not network.rpc_url:
        raise EvmRpcError(f"{network.display_name} is disabled")
    timeout = aiohttp.ClientTimeout(total=timeout_seconds)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        calls = [_rpc(session, network.rpc_url, "eth_getBalance", [address, "latest"], 1)]
        data = "0x70a08231" + address.removeprefix("0x").lower().zfill(64)
        calls.extend(_rpc(session, network.rpc_url, "eth_call", [{"to": token.address, "data": data}, "latest"], index)
                     for index, token in enumerate(network.tokens, 2))
        results = await asyncio.gather(*calls, return_exceptions=True)
    native = results[0]
    if isinstance(native, BaseException):
        raise EvmRpcError(f"{network.display_name} native balance failed") from native
    assets: list[WalletAsset] = []
    amount = _amount(native, 18)
    if amount:
        assets.append(WalletAsset(network.native_symbol, amount))
    for token, result in zip(network.tokens, results[1:], strict=True):
        if isinstance(result, str) and (token_amount := _amount(result, token.decimals)):
            assets.append(WalletAsset(token.symbol, token_amount, standard=token.standard))
    return WalletSnapshot(network.network_id, address, tuple(assets), "json_rpc", updated_at=datetime.now(timezone.utc))


async def _rpc(session: aiohttp.ClientSession, url: str, method: str, params: list[Any], request_id: int) -> Any:
    try:
        async with session.post(url, json={"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}) as response:
            if response.status == 429:
                raise EvmRpcError("RPC rate limit exceeded")
            if response.status >= 400:
                raise EvmRpcError(f"RPC HTTP {response.status}")
            payload = await response.json()
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
        raise EvmRpcError("RPC request failed") from exc
    if not isinstance(payload, dict) or "error" in payload or not isinstance(payload.get("result"), str):
        raise EvmRpcError("Malformed RPC response")
    return payload["result"]


def _amount(value: Any, decimals: int) -> float:
    try:
        return float(Decimal(int(value, 16)) / (Decimal(10) ** decimals))
    except (TypeError, ValueError):
        return 0.0
