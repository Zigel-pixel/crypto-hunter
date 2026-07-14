from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from app.utils.config import LIVE_CHART_REFRESH_SECONDS

logger = logging.getLogger(__name__)

ChartUpdater = Callable[[str, str], Awaitable[None]]


class LiveChartManager:
    """Own exactly one periodically refreshed chart task per chat."""
    def __init__(self, interval: float = LIVE_CHART_REFRESH_SECONDS) -> None:
        self._interval = interval
        self._tasks: dict[int, asyncio.Task[None]] = {}
        self._selection: dict[int, tuple[str, str]] = {}
        self._lock = asyncio.Lock()

    async def start_or_replace(self, key: int, asset: str, timeframe: str, updater: ChartUpdater) -> None:
        await self.stop(key)
        async with self._lock:
            self._selection[key] = (asset, timeframe)
            self._tasks[key] = asyncio.create_task(self._run(key, updater))

    async def update_selection(self, key: int, *, asset: str | None = None, timeframe: str | None = None) -> tuple[str, str]:
        current_asset, current_timeframe = self._selection.get(key, ("BTC", "1h"))
        selected = (asset or current_asset, timeframe or current_timeframe)
        self._selection[key] = selected
        return selected

    def selection(self, key: int) -> tuple[str, str]:
        return self._selection.get(key, ("BTC", "1h"))

    async def stop(self, key: int) -> bool:
        async with self._lock:
            task = self._tasks.pop(key, None)
        if task is None:
            return False
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        return True

    async def stop_all(self) -> None:
        await asyncio.gather(*(self.stop(key) for key in tuple(self._tasks)))

    def is_running(self, key: int) -> bool:
        return key in self._tasks and not self._tasks[key].done()

    async def _run(self, key: int, updater: ChartUpdater) -> None:
        try:
            while True:
                asset, timeframe = self.selection(key)
                await updater(asset, timeframe)
                await asyncio.sleep(self._interval)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Live chart task %s stopped: %s", key, exc)
        finally:
            current = asyncio.current_task()
            if self._tasks.get(key) is current:
                self._tasks.pop(key, None)


live_chart_manager = LiveChartManager()
