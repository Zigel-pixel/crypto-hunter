from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

import aiosqlite
from aiogram import BaseMiddleware, types
from aiogram.exceptions import TelegramBadRequest

from app.services.user_service import is_user_active

ALLOWED_STOPPED_TEXTS = {
    "/start",
    "/restart",
    "/stop",
    "▶️ Start",
    "🔄 Restart",
    "⏹ Stop",
}
logger = logging.getLogger(__name__)


class UserSessionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[types.TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: types.TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        try:
            active = user is None or await is_user_active(user.id)
        except aiosqlite.Error as exc:
            logger.exception("Could not read user session state: %s", exc)
            active = True
        if active:
            return await handler(event, data)

        if isinstance(event, types.Message):
            text = (event.text or "").split(maxsplit=1)[0].split("@", 1)[0]
            if text in ALLOWED_STOPPED_TEXTS:
                return await handler(event, data)
            return None

        if isinstance(event, types.CallbackQuery):
            try:
                await event.answer(
                    "Crypto Hunter is stopped. Press ▶️ Start or send /start.",
                    show_alert=True,
                )
            except TelegramBadRequest as exc:
                logger.debug("Could not answer an expired stopped-user callback: %s", exc)
        return None
