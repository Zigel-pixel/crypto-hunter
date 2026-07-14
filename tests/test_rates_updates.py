from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import SendMessage

from app.handlers.rates import _update_callback_message, build_rates_menu_keyboard, handle_rates_callback


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

    async def test_live_start_route_opens_btc_chart(self) -> None:
        message = SimpleNamespace(chat=SimpleNamespace(id=55))
        callback = SimpleNamespace(data="rates:live:start", message=message, from_user=SimpleNamespace(id=7), answer=AsyncMock())
        chart_message = SimpleNamespace()
        with patch("app.handlers.rates.get_setting", AsyncMock(return_value="English")), patch(
            "app.handlers.rates.show_live_chart", AsyncMock(return_value=chart_message)
        ) as chart, patch("app.handlers.rates.live_chart_manager.start_or_replace", AsyncMock()) as start:
            await handle_rates_callback(callback)
        chart.assert_awaited_once_with(message, 55, "BTC", "1h", "English")
        start.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
