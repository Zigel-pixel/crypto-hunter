from __future__ import annotations

import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import aiosqlite
from aiogram import types

from app.handlers import start as start_handler
from app.middlewares.user_session import UserSessionMiddleware
from app.services import settings_service, user_service
from app.services.settings_service import resolve_user_language
from app.services.user_service import activate_user, is_user_active, stop_user
from app.utils.i18n import translate


def _handler_message(user_id: int = 77, text: str = "/start") -> Mock:
    message = Mock()
    message.from_user = Mock(id=user_id)
    message.chat = Mock(id=user_id)
    message.text = text
    message.answer = AsyncMock()
    return message


def _middleware_message(text: str, user_id: int = 77) -> types.Message:
    return types.Message(
        message_id=1,
        date=datetime.now(timezone.utc),
        chat=types.Chat(id=user_id, type="private"),
        from_user=types.User(id=user_id, is_bot=False, first_name="Test"),
        text=text,
    )


def _reply_labels(message: Mock) -> set[str]:
    markup = message.answer.await_args.kwargs["reply_markup"]
    return {button.text for row in markup.keyboard for button in row}


class StartResponseLatencyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temporary_directory.name) / "start.db")
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "CREATE TABLE settings (telegram_id INTEGER, category TEXT, value TEXT, "
                "PRIMARY KEY (telegram_id, category))"
            )
            await db.execute(
                "CREATE TABLE users (telegram_id INTEGER PRIMARY KEY, "
                "is_active INTEGER NOT NULL DEFAULT 1)"
            )
            await db.commit()

    async def asyncTearDown(self) -> None:
        self.temporary_directory.cleanup()

    async def test_start_resolves_canonical_and_legacy_languages_without_writing(self) -> None:
        cases = (
            (1, "uk", "Ukrainian"),
            (2, "en", "English"),
            (3, "Ukrainian", "Ukrainian"),
            (4, "ua", "Ukrainian"),
            (5, "Українська", "Ukrainian"),
            (6, "uKrAiNiAn", "Ukrainian"),
            (7, "UA", "Ukrainian"),
            (8, "English", "English"),
            (9, "ENG", "English"),
            (10, "АНГЛІЙСЬКА", "English"),
            (11, "  ua  ", "Ukrainian"),
            (12, "  eNgLiSh  ", "English"),
        )
        async with aiosqlite.connect(self.db_path) as db:
            await db.executemany(
                "INSERT INTO settings (telegram_id, category, value) VALUES (?, 'language', ?)",
                ((telegram_id, stored) for telegram_id, stored, _ in cases),
            )
            await db.execute(
                "CREATE TRIGGER reject_settings_update BEFORE UPDATE ON settings "
                "BEGIN SELECT RAISE(FAIL, 'settings are read-only'); END"
            )
            await db.execute(
                "CREATE TRIGGER reject_settings_insert BEFORE INSERT ON settings "
                "BEGIN SELECT RAISE(FAIL, 'settings are read-only'); END"
            )
            await db.commit()

        with (
            patch.object(settings_service, "DB_NAME", self.db_path),
            patch.object(user_service, "DB_NAME", self.db_path),
            patch.object(start_handler.live_chart_manager, "stop", AsyncMock()),
        ):
            for telegram_id, stored, expected in cases:
                with self.subTest(stored=stored):
                    self.assertEqual(await resolve_user_language(telegram_id), expected)
                    message = _handler_message(telegram_id)
                    await start_handler.cmd_start(message, AsyncMock())
                    self.assertEqual(
                        message.answer.await_args.args[0],
                        translate("session.started", expected),
                    )
                    labels = _reply_labels(message)
                    expected_rates = "📈 Курси" if expected == "Ukrainian" else "📈 Rates"
                    self.assertIn(expected_rates, labels)

        async with aiosqlite.connect(self.db_path) as db:
            rows = await (
                await db.execute(
                    "SELECT telegram_id, value FROM settings ORDER BY telegram_id"
                )
            ).fetchall()
        self.assertEqual(rows, [(telegram_id, stored) for telegram_id, stored, _ in cases])

    async def test_start_calls_authoritative_resolver_once_and_builds_keyboard_in_memory(self) -> None:
        message = _handler_message()
        state = AsyncMock()
        with (
            patch.object(
                start_handler,
                "resolve_user_language",
                AsyncMock(return_value="Ukrainian"),
            ) as resolver,
            patch.object(start_handler, "activate_user", AsyncMock()),
            patch.object(start_handler.live_chart_manager, "stop", AsyncMock()),
        ):
            await start_handler.cmd_start(message, state)

        resolver.assert_awaited_once_with(
            77,
            timeout_seconds=start_handler.START_DB_TIMEOUT_SECONDS,
        )
        self.assertIn("📈 Курси", _reply_labels(message))
        self.assertNotIn("📈 Rates", _reply_labels(message))

    async def test_locked_language_read_falls_back_before_default_busy_timeout(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO settings (telegram_id, category, value) "
                "VALUES (77, 'language', 'uk')"
            )
            await db.commit()

        lock = await aiosqlite.connect(self.db_path, timeout=0)
        await lock.execute("BEGIN EXCLUSIVE")
        message = _handler_message()
        try:
            with (
                patch.object(settings_service, "DB_NAME", self.db_path),
                patch.object(start_handler, "activate_user", AsyncMock()),
                patch.object(start_handler.live_chart_manager, "stop", AsyncMock()),
            ):
                started_at = time.monotonic()
                await start_handler.cmd_start(message, AsyncMock())
                elapsed = time.monotonic() - started_at
        finally:
            await lock.rollback()
            await lock.close()

        self.assertLess(elapsed, 2.0)
        self.assertEqual(
            message.answer.await_args.args[0],
            translate("session.started", "English"),
        )
        self.assertIn("📈 Rates", _reply_labels(message))
        async with aiosqlite.connect(self.db_path) as db:
            stored = await (
                await db.execute(
                    "SELECT value FROM settings WHERE telegram_id=77 AND category='language'"
                )
            ).fetchone()
        self.assertEqual(stored, ("uk",))

    async def test_locked_activation_returns_prompt_localized_unavailable_reply(self) -> None:
        lock = await aiosqlite.connect(self.db_path, timeout=0)
        await lock.execute("BEGIN EXCLUSIVE")
        message = _handler_message()
        try:
            with (
                patch.object(user_service, "DB_NAME", self.db_path),
                patch.object(
                    start_handler,
                    "resolve_user_language",
                    AsyncMock(return_value="Ukrainian"),
                ),
                patch.object(start_handler.live_chart_manager, "stop", AsyncMock()),
            ):
                started_at = time.monotonic()
                await start_handler.cmd_start(message, AsyncMock())
                elapsed = time.monotonic() - started_at
        finally:
            await lock.rollback()
            await lock.close()

        self.assertLess(elapsed, 2.0)
        message.answer.assert_awaited_once_with(
            translate("session.unavailable", "Ukrainian")
        )
        async with aiosqlite.connect(self.db_path) as db:
            row = await (
                await db.execute("SELECT is_active FROM users WHERE telegram_id=77")
            ).fetchone()
        self.assertIsNone(row)

    async def test_recovery_writes_leave_no_transaction_or_lock(self) -> None:
        with patch.object(user_service, "DB_NAME", self.db_path):
            await activate_user(77)
            self.assertTrue(await is_user_active(77))
            await stop_user(77)
            self.assertFalse(await is_user_active(77))
            await activate_user(77)
            self.assertTrue(await is_user_active(77))

        verifier = await aiosqlite.connect(self.db_path, timeout=0.1)
        try:
            await verifier.execute("BEGIN EXCLUSIVE")
            await verifier.rollback()
        finally:
            await verifier.close()

    async def test_session_controls_bypass_state_read_in_all_languages(self) -> None:
        middleware = UserSessionMiddleware()
        handler = AsyncMock(return_value="handled")
        data = {
            "event_from_user": types.User(
                id=77,
                is_bot=False,
                first_name="Test",
            )
        }
        controls = (
            "/start",
            "/start@CryptoHunterBot",
            "/restart",
            "/stop",
            "▶️ Start",
            "▶️ Старт",
            "🔄 Restart",
            "🔄 Перезапустити",
            "⏹ Stop",
            "⏹ Зупинити",
        )
        with patch(
            "app.middlewares.user_session.is_user_active",
            new=AsyncMock(side_effect=AssertionError("state read must be bypassed")),
        ):
            for text in controls:
                with self.subTest(text=text):
                    handler.reset_mock()
                    result = await middleware(handler, _middleware_message(text), data)
                    self.assertEqual(result, "handled")
                    handler.assert_awaited_once()

    async def test_start_timing_logs_operations_without_private_values(self) -> None:
        private_user_id = 987654321
        private_text = "/start private-content"
        message = _handler_message(private_user_id, private_text)
        with (
            patch.object(
                start_handler,
                "resolve_user_language",
                AsyncMock(return_value="Ukrainian"),
            ),
            patch.object(start_handler, "activate_user", AsyncMock()),
            patch.object(start_handler.live_chart_manager, "stop", AsyncMock()),
            self.assertLogs("app.handlers.start", level="INFO") as captured,
        ):
            await start_handler.cmd_start(message, AsyncMock())

        output = "\n".join(captured.output)
        for operation in (
            "handler_entry",
            "user_session_read",
            "settings_database_read",
            "language_resolution",
            "normalization_persistence",
            "fsm_clear",
            "live_stop",
            "user_activation",
            "keyboard_build",
            "first_answer_send_start",
            "first_answer_send",
            "handler_total",
        ):
            self.assertIn(f"operation={operation}", output)
        self.assertRegex(output, r"duration_ms=\d+\.\d{3}")
        for private_value in (
            str(private_user_id),
            private_text,
            "private-content",
            "Ukrainian",
            "Ваш сеанс активний",
        ):
            self.assertNotIn(private_value, output)

    async def test_activation_error_details_are_not_logged(self) -> None:
        message = _handler_message()
        private_error = "database C:\\private\\session.db token=do-not-log"
        with (
            patch.object(
                start_handler,
                "resolve_user_language",
                AsyncMock(return_value="Ukrainian"),
            ),
            patch.object(
                start_handler,
                "activate_user",
                AsyncMock(side_effect=aiosqlite.OperationalError(private_error)),
            ),
            patch.object(start_handler.live_chart_manager, "stop", AsyncMock()),
            self.assertLogs("app.handlers.start", level="INFO") as captured,
        ):
            await start_handler.cmd_start(message, AsyncMock())

        output = "\n".join(captured.output)
        self.assertNotIn(private_error, output)
        self.assertNotIn("do-not-log", output)
        self.assertNotIn("private\\session.db", output)
        message.answer.assert_awaited_once_with(
            translate("session.unavailable", "Ukrainian")
        )


if __name__ == "__main__":
    unittest.main()
