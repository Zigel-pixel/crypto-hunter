"""Provider orchestration, retry handling, and short-lived wallet caching."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from time import perf_counter
from typing import Protocol

from app.integrations.blockchain.models import WalletSnapshot
from app.integrations.providers import ProviderError, ProviderNotConfigured
from app.integrations.providers import alchemy, moralis

CACHE_TTL_SECONDS = 60
MORALIS_RETRY_ATTEMPTS = 2

logger = logging.getLogger(__name__)


class WalletProvider(Protocol):
    """Contract implemented by blockchain wallet-data provider modules."""

    PROVIDER: str

    async def get_wallet(address: str) -> WalletSnapshot:
        """Fetch a wallet snapshot from the provider."""


class ProviderManagerError(RuntimeError):
    """Raised after no configured provider can retrieve wallet data."""


class ProviderManager:
    """Fetch wallet data with provider failover and an in-memory TTL cache."""

    def __init__(
        self,
        providers: Sequence[WalletProvider],
        cache_ttl_seconds: int = CACHE_TTL_SECONDS,
    ) -> None:
        self._providers = tuple(providers)
        self._cache_ttl = timedelta(seconds=cache_ttl_seconds)
        self._cache: dict[str, WalletSnapshot] = {}
        self._inflight: dict[str, asyncio.Task[WalletSnapshot]] = {}
        self._lock = asyncio.Lock()

    async def get_wallet(self, address: str) -> WalletSnapshot:
        """Return cached wallet data or fetch it once for concurrent callers."""
        cache_key = address.lower()
        async with self._lock:
            cached = self._cache.get(cache_key)
            if self._is_cache_valid(cached):
                return cached

            task = self._inflight.get(cache_key)
            if task is None:
                task = asyncio.create_task(self._fetch_wallet(address))
                self._inflight[cache_key] = task

        try:
            snapshot = await asyncio.shield(task)
        finally:
            if task.done():
                async with self._lock:
                    if self._inflight.get(cache_key) is task:
                        self._inflight.pop(cache_key, None)

        async with self._lock:
            self._cache[cache_key] = snapshot
        return snapshot

    def clear_cache(self) -> None:
        """Clear cached wallet data, primarily for controlled refreshes and tests."""
        self._cache.clear()

    def _is_cache_valid(self, snapshot: WalletSnapshot | None) -> bool:
        if snapshot is None or snapshot.updated_at is None:
            return False
        return datetime.now(timezone.utc) - snapshot.updated_at < self._cache_ttl

    async def _fetch_wallet(self, address: str) -> WalletSnapshot:
        configured_provider_found = False
        for provider in self._providers:
            attempts = (
                MORALIS_RETRY_ATTEMPTS
                if provider.PROVIDER == moralis.PROVIDER
                else 1
            )
            for _ in range(attempts):
                try:
                    return await self._fetch_from_provider(provider, address)
                except ProviderNotConfigured:
                    break
                except ProviderError:
                    configured_provider_found = True
                    logger.warning("[%s] Failed", provider.PROVIDER.title())
                except Exception:
                    configured_provider_found = True
                    logger.exception("[%s] Failed", provider.PROVIDER.title())

        if not configured_provider_found:
            raise ProviderManagerError(
                "Wallet providers are not configured. "
                "Set MORALIS_API_KEY or ALCHEMY_API_KEY."
            )
        raise ProviderManagerError(
            "Unable to retrieve wallet data. Please try again in a few moments."
        )

    async def _fetch_from_provider(
        self, provider: WalletProvider, address: str
    ) -> WalletSnapshot:
        started_at = perf_counter()
        snapshot = await provider.get_wallet(address)
        elapsed_ms = int((perf_counter() - started_at) * 1_000)
        logger.info("[%s] Success (%d ms)", provider.PROVIDER.title(), elapsed_ms)
        return replace(snapshot, updated_at=datetime.now(timezone.utc))


ethereum_provider_manager = ProviderManager((moralis, alchemy))
