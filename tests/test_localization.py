from __future__ import annotations

import unittest

from app.keyboards.main import build_main_keyboard
from app.models.news import NewsItem
from app.services.news_service import build_news_text
from app.utils.i18n import translate
from app.keyboards.alerts import build_alerts_keyboard
from app.keyboards.consultant import build_consultant_keyboard
from app.keyboards.wallet import build_wallet_detail_keyboard
from app.keyboards.settings import build_language_keyboard, build_settings_keyboard


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

    def test_nested_controls_follow_language_with_stable_callbacks(self) -> None:
        alerts = _button_texts(build_alerts_keyboard("Ukrainian"))
        consultant = _button_texts(build_consultant_keyboard("Ukrainian"))
        wallet = build_wallet_detail_keyboard(12, "Ukrainian")
        self.assertIn("🗑 Видалити сповіщення", alerts)
        self.assertIn("💬 Запитати консультанта", consultant)
        self.assertEqual(wallet.inline_keyboard[0][0].callback_data, "wallet:refresh:12")
        self.assertIn("Оновити", wallet.inline_keyboard[0][0].text)

    def test_settings_keyboards_are_fully_ukrainian(self) -> None:
        settings = _button_texts(build_settings_keyboard("Ukrainian"))
        languages = _button_texts(build_language_keyboard("Ukrainian"))
        self.assertEqual(settings, {"🌐 Мова", "💱 Валюта", "🕒 Часовий пояс", "⬅ Назад"})
        self.assertEqual(languages, {"Українська", "Англійська", "⬅ Назад"})


if __name__ == "__main__":
    unittest.main()
