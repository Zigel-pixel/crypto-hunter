from __future__ import annotations

import asyncio
import time
import logging
from collections import OrderedDict
from collections.abc import Awaitable, Callable

from app.models.news import NewsItem

Translator = Callable[[str, str], Awaitable[str]]
MAX_TEXT_LENGTH = 1200
logger = logging.getLogger(__name__)


class NewsTranslationService:
    def __init__(self, provider: Translator | None = None, *, timeout: float = 8, ttl: float = 3600,
                 max_entries: int = 256, concurrency: int = 3) -> None:
        self.provider = provider
        self.timeout, self.ttl, self.max_entries = timeout, ttl, max_entries
        self._cache: OrderedDict[tuple[str, str], tuple[float, str]] = OrderedDict()
        self._inflight: dict[tuple[str, str], asyncio.Task[str | None]] = {}
        self._lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(concurrency)

    async def localize(self, items: list[NewsItem], language: str) -> list[NewsItem]:
        if language != "Ukrainian":
            return items
        return list(await asyncio.gather(*(self._localize_item(item) for item in items)))

    async def _localize_item(self, item: NewsItem) -> NewsItem:
        if self.provider is None:
            return NewsItem(item.title, item.url, item.published_at, item.summary, translation_fallback=True)
        title, summary = await asyncio.gather(self._translate(item.title), self._translate(item.summary) if item.summary else _none())
        if title is None:
            return NewsItem(item.title, item.url, item.published_at, item.summary, translation_fallback=True)
        return NewsItem(title, item.url, item.published_at, summary if item.summary else None,
                        original_title=item.title, translation_fallback=summary is None and item.summary is not None)

    async def _translate(self, text: str | None) -> str | None:
        if not text:
            return None
        bounded = text.strip()[:MAX_TEXT_LENGTH]
        key = (" ".join(bounded.casefold().split()), "uk")
        now = time.monotonic()
        async with self._lock:
            cached = self._cache.get(key)
            if cached and now - cached[0] < self.ttl:
                self._cache.move_to_end(key)
                return cached[1]
            task = self._inflight.get(key)
            if task is None:
                task = asyncio.create_task(self._call_provider(bounded))
                self._inflight[key] = task
        try:
            result = await asyncio.shield(task)
        finally:
            if task.done():
                async with self._lock:
                    self._inflight.pop(key, None)
        if result:
            async with self._lock:
                self._cache[key] = (time.monotonic(), result)
                self._cache.move_to_end(key)
                while len(self._cache) > self.max_entries:
                    self._cache.popitem(last=False)
        return result

    async def _call_provider(self, text: str) -> str | None:
        try:
            async with self._semaphore:
                result = await asyncio.wait_for(self.provider(text, "uk"), timeout=self.timeout)  # type: ignore[misc]
            cleaned = " ".join(result.split())
            return cleaned[:MAX_TEXT_LENGTH] or None
        except Exception as exc:
            logger.warning("News translation unavailable (%s)", type(exc).__name__)
            return None


async def _none() -> None:
    return None


news_translation_service = NewsTranslationService()
