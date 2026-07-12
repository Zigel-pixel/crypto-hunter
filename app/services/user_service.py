from __future__ import annotations

import aiosqlite

DB_NAME = "crypto.db"


async def activate_user(telegram_id: int) -> None:
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """
            INSERT INTO users (telegram_id, is_active)
            VALUES (?, 1)
            ON CONFLICT(telegram_id) DO UPDATE SET is_active = 1
            """,
            (telegram_id,),
        )
        await db.commit()


async def stop_user(telegram_id: int) -> None:
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """
            INSERT INTO users (telegram_id, is_active)
            VALUES (?, 0)
            ON CONFLICT(telegram_id) DO UPDATE SET is_active = 0
            """,
            (telegram_id,),
        )
        await db.commit()


async def is_user_active(telegram_id: int) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT is_active FROM users WHERE telegram_id = ?", (telegram_id,)
        )
        row = await cursor.fetchone()
    return row is None or bool(row[0])
