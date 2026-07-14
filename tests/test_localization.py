from __future__ import annotations

import unittest

from app.keyboards.main import build_main_keyboard
from app.models.news import NewsItem
from app.services.news_service import build_news_text
from app.utils.i18n import translate


def _button_texts(markup: object) -> set[str]:
    return {button.text for row in markup.keyboard for button in row}  # type: ignore[attr-defined]


class LocalizationTests(unittest.TestCase):
    def test_main_menu_languages(self) -> None:
        english = _button_texts(build_main_keyboard("English"))
        ukrainian = _button_texts(build_main_keyboard("Ukrainian"))
        self.assertIn("📊 Assets", english)
        self.assertIn("🔔 Alerts", english)
        self.assertIn("📊 Активи", ukrainian)
        self.assertIn("🔔 Сповіщення", ukrainian)
        self.assertIn("▶️ Старт", ukrainian)
        self.assertIn("🔄 Перезапустити", ukrainian)
        self.assertIn("⏹ Зупинити", ukrainian)

    def test_news_title_follows_language(self) -> None:
        item = NewsItem("Headline", "https://example.com", None)
        self.assertTrue(build_news_text([item], "English").startswith("📰 Latest crypto news"))
        self.assertTrue(build_news_text([item], "Ukrainian").startswith("📰 Останні криптоновини"))

    def test_missing_key_falls_back_safely(self) -> None:
        self.assertEqual(translate("missing.key", "Ukrainian"), "missing.key")


if __name__ == "__main__":
    unittest.main()
