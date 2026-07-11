from __future__ import annotations

from typing import Optional

import aiosqlite

DB_NAME = "crypto.db"


async def upsert_setting(telegram_id: int, category: str, value: str) -> None:
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """
            INSERT INTO settings (telegram_id, category, value)
            VALUES (?, ?, ?)
            ON CONFLICT(telegram_id, category) DO UPDATE SET value = excluded.value
            """,
            (telegram_id, category, value),
        )
        await db.commit()


async def get_setting(telegram_id: int, category: str) -> Optional[str]:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT value FROM settings WHERE telegram_id = ? AND category = ?",
            (telegram_id, category),
        )
        row = await cursor.fetchone()
        return row[0] if row else None
