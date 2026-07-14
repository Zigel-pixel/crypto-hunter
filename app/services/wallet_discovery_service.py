from __future__ import annotations

import asyncio
import time

from app.integrations.blockchain import tron
from app.integrations.blockchain.evm_rpc import get_wallet as get_evm_wallet
from app.integrations.blockchain.network_registry import enabled_evm_networks
from app.models.wallet_address import AddressFamily
from app.models.wallet_discovery import WalletDiscoveryResult
from app.services.wallet_address_service import detect_wallet_address
from app.utils.config import WALLET_MAX_CONCURRENT_SCANS, WALLET_SCAN_TIMEOUT_SECONDS

_locks: dict[str, asyncio.Lock] = {}
_last_scan: dict[str, float] = {}
SCAN_COOLDOWN_SECONDS = 3.0


async def discover_wallet(value: str, *, bypass_cooldown: bool = False) -> WalletDiscoveryResult:
    address = detect_wallet_address(value)
    if address is None:
        raise ValueError("Invalid or unsupported wallet address")
    lock = _locks.setdefault(address.comparison_address, asyncio.Lock())
    async with lock:
        now = time.monotonic()
        if not bypass_cooldown and now - _last_scan.get(address.comparison_address, 0) < SCAN_COOLDOWN_SECONDS:
            raise RuntimeError("Wallet scan cooldown is active")
        _last_scan[address.comparison_address] = now
        if address.family is AddressFamily.TRON:
            try:
                snapshot = await asyncio.wait_for(tron.get_wallet(address.display_address), WALLET_SCAN_TIMEOUT_SECONDS)
                return WalletDiscoveryResult(address, ("tron",), (snapshot,) if snapshot.assets else ())
            except Exception:
                return WalletDiscoveryResult(address, ("tron",), (), ("TRON provider unavailable",))

        networks = enabled_evm_networks()
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
                (f"{network.display_name} provider unavailable",)
                if isinstance(result, BaseException)
                else result.warnings
            )
        )
        return WalletDiscoveryResult(address, tuple(item.network_id for item in networks), active, warnings)
