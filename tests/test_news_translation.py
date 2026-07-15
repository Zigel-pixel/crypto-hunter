import asyncio
import unittest

from app.models.news import NewsItem
from app.services.news_service import build_news_text
from app.services.news_translation_service import MAX_TEXT_LENGTH, NewsTranslationService


class NewsTranslationTests(unittest.IsolatedAsyncioTestCase):
    async def test_ukrainian_translation_preserves_metadata_and_absent_summary(self) -> None:
        async def provider(text, language): return f"Переклад: {text}"
        service = NewsTranslationService(provider)
        item = NewsItem("Bitcoin ETF approved", "https://example.com/a", None)
        translated = (await service.localize([item], "Ukrainian"))[0]
        self.assertEqual(translated.url, item.url)
        self.assertIsNone(translated.summary)
        self.assertIn("Переклад", translated.title)
        self.assertIn("Bitcoin", translated.title)

    async def test_english_bypasses_provider(self) -> None:
        calls = 0
        async def provider(text, language):
            nonlocal calls; calls += 1; return text
        item = NewsItem("Original", "https://example.com", None, "Summary")
        result = await NewsTranslationService(provider).localize([item], "English")
        self.assertEqual(result, [item]); self.assertEqual(calls, 0)

    async def test_cache_and_concurrent_deduplication(self) -> None:
        calls = 0
        async def provider(text, language):
            nonlocal calls; calls += 1; await asyncio.sleep(0); return "Переклад"
        service = NewsTranslationService(provider)
        item = NewsItem("Same", "https://example.com", None)
        await asyncio.gather(service.localize([item], "Ukrainian"), service.localize([item], "Ukrainian"))
        await service.localize([item], "Ukrainian")
        self.assertEqual(calls, 1)

    async def test_timeout_and_missing_provider_fall_back_safely(self) -> None:
        async def slow(text, language): await asyncio.sleep(1); return "late"
        item = NewsItem("Original", "https://example.com", None, "Summary")
        for service in (NewsTranslationService(None), NewsTranslationService(slow, timeout=0.001)):
            result = (await service.localize([item], "Ukrainian"))[0]
            self.assertEqual(result.title, "Original")
            self.assertTrue(result.translation_fallback)
            self.assertIn("показано оригінал", build_news_text([result], "Ukrainian"))

    async def test_long_text_is_bounded(self) -> None:
        seen = ""
        async def provider(text, language):
            nonlocal seen; seen = text; return text
        await NewsTranslationService(provider).localize([NewsItem("x" * 5000, "https://example.com", None)], "Ukrainian")
        self.assertEqual(len(seen), MAX_TEXT_LENGTH)
