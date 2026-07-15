from __future__ import annotations

import asyncio
import time

from app.integrations.blockchain import tron
from app.integrations.blockchain.errors import ProviderErrorCode, classify_provider_error
from app.integrations.blockchain.evm_rpc import get_wallet as get_evm_wallet
from app.integrations.blockchain.network_registry import enabled_evm_networks
from app.models.wallet_address import AddressFamily
from app.models.wallet_discovery import WalletDiscoveryResult
from app.services.wallet_address_service import detect_wallet_address
from app.utils.config import WALLET_BALANCE_CACHE_SECONDS, WALLET_MAX_CONCURRENT_SCANS, WALLET_SCAN_TIMEOUT_SECONDS

_locks: dict[str, asyncio.Lock] = {}
_last_scan: dict[str, float] = {}
_cache: dict[str, tuple[float, WalletDiscoveryResult]] = {}
SCAN_COOLDOWN_SECONDS = 3.0


async def discover_wallet(value: str, *, bypass_cooldown: bool = False) -> WalletDiscoveryResult:
    address = detect_wallet_address(value)
    if address is None:
        raise ValueError("Invalid or unsupported wallet address")
    lock = _locks.setdefault(address.comparison_address, asyncio.Lock())
    async with lock:
        now = time.monotonic()
        cached = _cache.get(address.comparison_address)
        if not bypass_cooldown and cached and now - cached[0] < WALLET_BALANCE_CACHE_SECONDS:
            return cached[1]
        if not bypass_cooldown and now - _last_scan.get(address.comparison_address, 0) < SCAN_COOLDOWN_SECONDS:
            raise RuntimeError("Wallet scan cooldown is active")
        _last_scan[address.comparison_address] = now
        if address.family is AddressFamily.TRON:
            try:
                snapshot = await asyncio.wait_for(tron.get_wallet(address.display_address), WALLET_SCAN_TIMEOUT_SECONDS)
                result = WalletDiscoveryResult(address, ("tron",), (snapshot,))
                _cache[address.comparison_address] = (time.monotonic(), result)
                return result
            except Exception as exc:
                code = classify_provider_error(exc)
                if cached:
                    stale = WalletDiscoveryResult(address, ("tron",), cached[1].active, (code,), True)
                    return stale
                return WalletDiscoveryResult(address, ("tron",), (), (code,))

        # Address auto-detection in this sprint maps EVM syntax to Ethereum;
        # legacy chain integrations remain available to their existing callers.
        networks = tuple(item for item in enabled_evm_networks() if item.network_id == "ethereum")
        semaphore = asyncio.Semaphore(WALLET_MAX_CONCURRENT_SCANS)
        async def scan(network):
            async with semaphore:
                return await asyncio.wait_for(get_evm_wallet(network, address.display_address, WALLET_SCAN_TIMEOUT_SECONDS), WALLET_SCAN_TIMEOUT_SECONDS)
        results = await asyncio.gather(*(scan(network) for network in networks), return_exceptions=True)
        active = tuple(result for result in results if not isinstance(result, BaseException) and result.assets)
        warnings = tuple(
            warning
            for network, result in zip(networks, results, strict=True)
            for warning in (
                (classify_provider_error(result),)
                if isinstance(result, BaseException)
                else result.warnings
            )
        )
        result = WalletDiscoveryResult(address, tuple(item.network_id for item in networks), active, warnings)
        if active:
            _cache[address.comparison_address] = (time.monotonic(), result)
        elif cached:
            return WalletDiscoveryResult(address, result.scanned_networks, cached[1].active, warnings, True)
        return result
