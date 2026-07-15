from unittest.mock import AsyncMock, Mock, patch
import unittest

from app.handlers.settings import save_language


class SettingsLanguageTests(unittest.IsolatedAsyncioTestCase):
    async def test_save_ukrainian_persists_canonical_value_and_returns_ukrainian_main_keyboard(self) -> None:
        message = Mock(text="Українська", from_user=Mock(id=77))
        message.answer = AsyncMock()
        state = AsyncMock()
        with patch("app.handlers.settings.upsert_setting", AsyncMock()) as upsert:
            await save_language(message, state)
        upsert.assert_awaited_once_with(77, "language", "Ukrainian")
        markup = message.answer.await_args.kwargs["reply_markup"]
        labels = {button.text for row in markup.keyboard for button in row}
        self.assertIn("⚙ Налаштування", labels)
        self.assertIn("📊 Активи", labels)
        self.assertNotIn("⚙ Settings", labels)
