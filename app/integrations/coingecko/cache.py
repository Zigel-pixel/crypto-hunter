from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from time import monotonic
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class _CacheEntry(Generic[T]):
    value: T
    stored_at: float


class AsyncTTLCache(Generic[T]):
    """Small in-memory cache with request coalescing and stale fallback."""

    def __init__(
        self,
        ttl_seconds: float,
        stale_ttl_seconds: float,
        logger: logging.Logger,
        namespace: str = "Provider",
    ) -> None:
        self._ttl_seconds = ttl_seconds
        self._stale_ttl_seconds = stale_ttl_seconds
        self._logger = logger
        self._namespace = namespace
        self._entries: dict[str, _CacheEntry[T]] = {}
        self._inflight: dict[str, asyncio.Task[T]] = {}
        self._stale_keys: set[str] = set()
        self._lock = asyncio.Lock()

    async def get(
        self,
        key: str,
        loader: Callable[[], Awaitable[T]],
        *,
        force_refresh: bool = False,
        min_refresh_interval: float = 0,
    ) -> T:
        now = monotonic()
        created_task = False
        async with self._lock:
            entry = self._entries.get(key)
            age = now - entry.stored_at if entry is not None else None
            if entry is not None and (
                (not force_refresh and age <= self._ttl_seconds)
                or (force_refresh and age <= min_refresh_interval)
            ):
                self._logger.debug("%s cache hit: %s", self._namespace, key)
                return entry.value

            task = self._inflight.get(key)
            if task is None:
                task = asyncio.create_task(loader())
                self._inflight[key] = task
                created_task = True
            else:
                self._logger.debug(
                    "%s request joined in flight: %s", self._namespace, key
                )

        try:
            value = await asyncio.shield(task)
        except Exception as exc:
            stale = self._entries.get(key)
            if (
                stale is not None
                and monotonic() - stale.stored_at <= self._stale_ttl_seconds
            ):
                log = self._logger.warning if created_task else self._logger.debug
                log(
                    "%s request failed for %s; using stale cache: %s",
                    self._namespace,
                    key,
                    exc,
                )
                self._stale_keys.add(key)
                return stale.value
            if created_task:
                self._logger.warning(
                    "%s request failed for %s with no usable cache: %s",
                    self._namespace, key, exc,
                )
            raise
        else:
            async with self._lock:
                self._entries[key] = _CacheEntry(value=value, stored_at=monotonic())
                self._stale_keys.discard(key)
            return value
        finally:
            if task.done():
                async with self._lock:
                    if self._inflight.get(key) is task:
                        self._inflight.pop(key, None)

    def clear(self) -> None:
        self._entries.clear()
        self._stale_keys.clear()

    def is_stale(self, key: str) -> bool:
        return key in self._stale_keys

    def is_inflight(self, key: str) -> bool:
        task = self._inflight.get(key)
        return task is not None and not task.done()
