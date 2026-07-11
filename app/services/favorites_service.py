from __future__ import annotations

from typing import List

import aiosqlite

DB_NAME = "crypto.db"


async def add_favorite(telegram_id: int, coin: str) -> None:
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR IGNORE INTO favorites (telegram_id, coin) VALUES (?, ?)",
            (telegram_id, coin),
        )
        await db.commit()


async def get_favorites(telegram_id: int) -> List[str]:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT coin FROM favorites WHERE telegram_id = ? ORDER BY coin",
            (telegram_id,),
        )
        rows = await cursor.fetchall()
        return [row[0] for row in rows]


async def remove_favorite(telegram_id: int, coin: str) -> None:
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "DELETE FROM favorites WHERE telegram_id = ? AND coin = ?",
            (telegram_id, coin),
        )
        await db.commit()
