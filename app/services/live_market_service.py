from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from app.integrations.live import BinanceLiveProvider
from app.integrations.live.base import LiveMarketProvider
from app.models.live_market import LiveQuote

LiveUpdater = Callable[[dict[str, LiveQuote]], Awaitable[None]]
UPDATE_INTERVAL_SECONDS = 2.5
logger = logging.getLogger(__name__)


class LiveTaskManager:
    def __init__(
        self,
        provider: LiveMarketProvider | None = None,
        update_interval: float = UPDATE_INTERVAL_SECONDS,
    ) -> None:
        self._provider = provider or BinanceLiveProvider()
        self._update_interval = update_interval
        self._tasks: dict[int, asyncio.Task[None]] = {}
        self._lock = asyncio.Lock()

    async def start(self, key: int, updater: LiveUpdater) -> bool:
        async with self._lock:
            existing = self._tasks.get(key)
            if existing is not None and not existing.done():
                return False
            task = asyncio.create_task(self._run(updater))
            self._tasks[key] = task
            task.add_done_callback(lambda completed: self._remove_done(key, completed))
            return True

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
        async with self._lock:
            keys = tuple(self._tasks)
        await asyncio.gather(*(self.stop(key) for key in keys))

    def is_running(self, key: int) -> bool:
        task = self._tasks.get(key)
        return task is not None and not task.done()

    async def _run(self, updater: LiveUpdater) -> None:
        latest: dict[str, LiveQuote] = {}
        last_display: tuple[tuple[str, str], ...] = ()

        async def on_quote(quote: LiveQuote) -> None:
            latest[quote.symbol] = quote

        provider_task = asyncio.create_task(self._provider.run(on_quote))
        try:
            while True:
                await asyncio.sleep(self._update_interval)
                display = tuple(
                    sorted(
                        (symbol, f"{quote.price:.2f}")
                        for symbol, quote in latest.items()
                    )
                )
                if latest and display != last_display:
                    await updater(dict(latest))
                    last_display = display
        finally:
            provider_task.cancel()
            try:
                await provider_task
            except asyncio.CancelledError:
                pass

    def _remove_done(self, key: int, task: asyncio.Task[None]) -> None:
        if self._tasks.get(key) is task:
            self._tasks.pop(key, None)
        if not task.cancelled() and (error := task.exception()) is not None:
            logger.warning("Live market task %s stopped unexpectedly: %s", key, error)


live_task_manager = LiveTaskManager()
