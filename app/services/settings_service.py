from __future__ import annotations

from typing import Optional

import aiosqlite

from app.utils.i18n import canonical_language, normalize_language

DB_NAME = "crypto.db"


async def upsert_setting(telegram_id: int, category: str, value: str) -> None:
    stored_value = canonical_language(value) if category == "language" else value
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """
            INSERT INTO settings (telegram_id, category, value)
            VALUES (?, ?, ?)
            ON CONFLICT(telegram_id, category) DO UPDATE SET value = excluded.value
            """,
            (telegram_id, category, stored_value),
        )
        await db.commit()


async def get_setting(telegram_id: int, category: str) -> Optional[str]:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT value FROM settings WHERE telegram_id = ? AND category = ?",
            (telegram_id, category),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return normalize_language(row[0]) if category == "language" else row[0]


async def resolve_user_language(telegram_id: int) -> str:
    """Authoritative persisted language resolver for handlers and callbacks."""
    return normalize_language(await get_setting(telegram_id, "language"))
