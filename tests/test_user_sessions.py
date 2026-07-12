from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import aiosqlite
from aiogram import types

from app.middlewares.user_session import UserSessionMiddleware
from app.services import user_service
from app.services.user_service import activate_user, is_user_active, stop_user


class UserSessionServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "test.db")
        self.original_db = user_service.DB_NAME
        user_service.DB_NAME = self.db_path
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE users (
                    telegram_id INTEGER PRIMARY KEY,
                    is_active INTEGER NOT NULL DEFAULT 1
                )
                """
            )
            await db.execute(
                "CREATE TABLE favorites (telegram_id INTEGER, coin TEXT, PRIMARY KEY (telegram_id, coin))"
            )
            await db.commit()

    async def asyncTearDown(self) -> None:
        user_service.DB_NAME = self.original_db
        self.temp_dir.cleanup()

    async def test_repeated_start_is_safe_and_reactivates_stopped_user(self) -> None:
        await activate_user(1)
        await activate_user(1)
        self.assertTrue(await is_user_active(1))
        await stop_user(1)
        self.assertFalse(await is_user_active(1))
        await activate_user(1)
        self.assertTrue(await is_user_active(1))

    async def test_stopping_one_user_does_not_affect_another_or_data(self) -> None:
        await activate_user(1)
        await activate_user(2)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT INTO favorites VALUES (1, 'BTC')")
            await db.commit()
        await stop_user(1)
        self.assertFalse(await is_user_active(1))
        self.assertTrue(await is_user_active(2))
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT coin FROM favorites WHERE telegram_id = 1"
            )
            row = await cursor.fetchone()
        self.assertEqual(row, ("BTC",))


class UserSessionMiddlewareTests(unittest.IsolatedAsyncioTestCase):
    def _message(self, text: str) -> types.Message:
        user = types.User(id=1, is_bot=False, first_name="Test")
        return types.Message(
            message_id=1,
            date=datetime.now(timezone.utc),
            chat=types.Chat(id=1, type="private"),
            from_user=user,
            text=text,
        )

    async def test_stopped_user_is_blocked_but_start_is_allowed(self) -> None:
        middleware = UserSessionMiddleware()
        handler = AsyncMock(return_value="handled")
        data = {"event_from_user": types.User(id=1, is_bot=False, first_name="Test")}
        with patch(
            "app.middlewares.user_session.is_user_active",
            new=AsyncMock(return_value=False),
        ):
            result = await middleware(handler, self._message("📈 Rates"), data)
            self.assertIsNone(result)
            handler.assert_not_awaited()

            result = await middleware(handler, self._message("/start"), data)
            self.assertEqual(result, "handled")
            handler.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
