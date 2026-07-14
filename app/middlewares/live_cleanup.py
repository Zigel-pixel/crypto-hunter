from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware, types

from app.services.live_market_service import live_chart_manager, live_task_manager


class LiveCleanupMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[types.TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: types.TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, types.Message):
            await live_task_manager.stop(event.chat.id)
            await live_chart_manager.stop(event.chat.id)
        elif (
            isinstance(event, types.CallbackQuery)
            and event.message is not None
            and not (event.data or "").startswith("rates:live:")
        ):
            await live_task_manager.stop(event.message.chat.id)
            await live_chart_manager.stop(event.message.chat.id)
        return await handler(event, data)
