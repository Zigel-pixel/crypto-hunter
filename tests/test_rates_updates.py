from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import SendMessage

from app.handlers.rates import _update_callback_message, build_rates_menu_keyboard


class RatesMessageUpdateTests(unittest.IsolatedAsyncioTestCase):
    async def test_text_message_uses_edit_text(self) -> None:
        message = SimpleNamespace(
            text="old", caption=None, edit_text=AsyncMock(), edit_caption=AsyncMock(), answer=AsyncMock()
        )
        callback = SimpleNamespace(message=message)

        await _update_callback_message(callback, "new", build_rates_menu_keyboard())

        message.edit_text.assert_awaited_once()
        message.edit_caption.assert_not_awaited()
        message.answer.assert_not_awaited()

    async def test_media_caption_uses_edit_caption(self) -> None:
        message = SimpleNamespace(
            text=None, caption="old", edit_text=AsyncMock(), edit_caption=AsyncMock(), answer=AsyncMock()
        )
        callback = SimpleNamespace(message=message)

        await _update_callback_message(callback, "new", build_rates_menu_keyboard())

        message.edit_caption.assert_awaited_once()
        message.edit_text.assert_not_awaited()
        message.answer.assert_not_awaited()

    async def test_message_without_text_or_caption_sends_new_message(self) -> None:
        message = SimpleNamespace(
            text=None, caption=None, edit_text=AsyncMock(), edit_caption=AsyncMock(), answer=AsyncMock()
        )
        callback = SimpleNamespace(message=message)

        await _update_callback_message(callback, "new", build_rates_menu_keyboard())

        message.answer.assert_awaited_once()
        message.edit_text.assert_not_awaited()
        message.edit_caption.assert_not_awaited()

    async def test_bad_request_falls_back_to_new_message(self) -> None:
        error = TelegramBadRequest(
            method=SendMessage(chat_id=1, text="new"),
            message="there is no text in the message to edit",
        )
        message = SimpleNamespace(
            text="old",
            caption=None,
            edit_text=AsyncMock(side_effect=error),
            edit_caption=AsyncMock(),
            answer=AsyncMock(),
        )
        callback = SimpleNamespace(message=message)

        await _update_callback_message(callback, "new", build_rates_menu_keyboard())

        message.answer.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
