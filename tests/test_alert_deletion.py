from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import aiosqlite

from app.keyboards.alerts import build_delete_alert_keyboard
from app.services import alerts_service
from app.services.alert_formatter import format_alert


ALERT = {"id": 42, "coin": "BTC", "condition": ">", "target_price": 70000.0}


class AlertFormattingTests(unittest.TestCase):
    def test_descriptive_button_uses_stable_id(self) -> None:
        keyboard = build_delete_alert_keyboard([ALERT])
        button = keyboard.inline_keyboard[0][0]
        self.assertIn("BTC above $70,000", button.text)
        self.assertEqual(button.callback_data, "alert:delete:select:42")

    def test_ukrainian_formatter(self) -> None:
        self.assertIn("BTC вище $70 000", format_alert(ALERT, "Ukrainian"))


class AlertDeletionTests(unittest.IsolatedAsyncioTestCase):
    async def test_repeated_delete_does_not_delete_another_alert(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db = str(Path(directory) / "alerts.db")
            original = alerts_service.DB_NAME
            alerts_service.DB_NAME = db
            try:
                async with aiosqlite.connect(db) as connection:
                    await connection.execute("CREATE TABLE alerts (id INTEGER PRIMARY KEY, telegram_id INTEGER, coin TEXT, condition TEXT, target_price REAL, created_at TEXT)")
                    await connection.executemany("INSERT INTO alerts VALUES (?,?,?,?,?,?)", [(1, 7, "BTC", ">", 1, "x"), (2, 7, "ETH", "<", 2, "x")])
                    await connection.commit()
                self.assertTrue(await alerts_service.delete_alert(1, 7))
                self.assertFalse(await alerts_service.delete_alert(1, 7))
                self.assertIsNotNone(await alerts_service.get_alert(2, 7))
            finally:
                alerts_service.DB_NAME = original
