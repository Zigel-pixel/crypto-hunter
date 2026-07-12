from __future__ import annotations

import asyncio
import logging
import unittest

from app.integrations.coingecko.cache import AsyncTTLCache


class AsyncTTLCacheTests(unittest.IsolatedAsyncioTestCase):
    async def test_concurrent_requests_share_loader(self) -> None:
        cache: AsyncTTLCache[str] = AsyncTTLCache(60, 300, logging.getLogger(__name__))
        calls = 0

        async def loader() -> str:
            nonlocal calls
            calls += 1
            await asyncio.sleep(0.01)
            return "market-data"

        results = await asyncio.gather(*(cache.get("btc", loader) for _ in range(5)))

        self.assertEqual(results, ["market-data"] * 5)
        self.assertEqual(calls, 1)

    async def test_stale_value_is_used_when_loader_fails(self) -> None:
        cache: AsyncTTLCache[str] = AsyncTTLCache(0, 300, logging.getLogger(__name__))

        async def successful_loader() -> str:
            return "last-real-value"

        async def failing_loader() -> str:
            raise RuntimeError("provider unavailable")

        self.assertEqual(await cache.get("btc", successful_loader), "last-real-value")
        await asyncio.sleep(0)
        self.assertEqual(await cache.get("btc", failing_loader), "last-real-value")

    async def test_manual_refresh_respects_short_cooldown(self) -> None:
        cache: AsyncTTLCache[str] = AsyncTTLCache(60, 300, logging.getLogger(__name__))
        calls = 0

        async def loader() -> str:
            nonlocal calls
            calls += 1
            return f"value-{calls}"

        self.assertEqual(await cache.get("btc", loader), "value-1")
        self.assertEqual(
            await cache.get(
                "btc", loader, force_refresh=True, min_refresh_interval=3
            ),
            "value-1",
        )
        self.assertEqual(calls, 1)


if __name__ == "__main__":
    unittest.main()
