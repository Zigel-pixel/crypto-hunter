from __future__ import annotations

import asyncio
import unittest
from datetime import datetime, timezone

from app.models.live_market import LiveQuote
from app.services.live_market_service import LiveTaskManager


class FakeLiveProvider:
    def __init__(self) -> None:
        self.cancelled = False

    async def run(self, on_quote) -> None:
        try:
            await on_quote(LiveQuote("BTC", 100.0, datetime.now(timezone.utc), "test"))
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled = True
            raise


class LiveTaskManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_deduplicates_and_stop_cancels_provider(self) -> None:
        provider = FakeLiveProvider()
        manager = LiveTaskManager(provider=provider, update_interval=0.01)
        updated = asyncio.Event()

        async def updater(quotes) -> None:
            if "BTC" in quotes:
                updated.set()

        self.assertTrue(await manager.start(123, updater))
        self.assertFalse(await manager.start(123, updater))
        await asyncio.wait_for(updated.wait(), timeout=1)
        self.assertTrue(manager.is_running(123))
        self.assertTrue(await manager.stop(123))
        self.assertFalse(manager.is_running(123))
        self.assertTrue(provider.cancelled)


if __name__ == "__main__":
    unittest.main()
