from __future__ import annotations

import asyncio
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from app.services.chart_service import TIMEFRAME_SECONDS, build_timeframe_chart, render_chart
from app.services.live_market_service import LiveChartManager


class LiveChartRenderingTests(unittest.IsolatedAsyncioTestCase):
    def test_flat_series_renders_png(self) -> None:
        now = datetime.now(timezone.utc)
        data = render_chart([(now, 10), (now + timedelta(minutes=1), 10)], "Flat")
        self.assertTrue(data.startswith(b"\x89PNG"))

    async def test_timeframe_filters_real_points(self) -> None:
        now = datetime.now(timezone.utc)
        points = [(now - timedelta(hours=2), 1), (now - timedelta(minutes=30), 2), (now, 3)]
        with patch("app.services.chart_service.fetch_price_history", AsyncMock(return_value=points)):
            result = await build_timeframe_chart("bitcoin", "BTC", "1h")
        self.assertIsNotNone(result)
        self.assertEqual(len(result[1]), 2)

    async def test_sparse_series_returns_none(self) -> None:
        with patch("app.services.chart_service.fetch_price_history", AsyncMock(return_value=[(datetime.now(timezone.utc), 1)])):
            self.assertIsNone(await build_timeframe_chart("bitcoin", "BTC", "15m"))

    def test_supported_timeframes(self) -> None:
        self.assertEqual(set(TIMEFRAME_SECONDS), {"15m", "1h", "4h", "24h", "7d"})


class LiveChartManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_replace_and_stop_owns_one_task(self) -> None:
        manager = LiveChartManager(interval=60)
        updater = AsyncMock()
        await manager.start_or_replace(1, "BTC", "1h", updater)
        first = manager._tasks[1]
        await asyncio.sleep(0)
        await manager.start_or_replace(1, "ETH", "4h", updater)
        self.assertTrue(first.cancelled())
        self.assertEqual(manager.selection(1), ("ETH", "4h"))
        self.assertTrue(await manager.stop(1))
        self.assertFalse(manager.is_running(1))
