from __future__ import annotations

import aiosqlite

from app.models.asset import AssetDefinition
from app.utils.assets import ASSET_REGISTRY

DB_NAME = "crypto.db"


async def add_favorite(telegram_id: int, coin: str) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "INSERT OR IGNORE INTO favorites (telegram_id, coin) VALUES (?, ?)",
            (telegram_id, coin),
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_favorites(telegram_id: int) -> list[str]:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT coin FROM favorites WHERE telegram_id = ? ORDER BY coin",
            (telegram_id,),
        )
        rows = await cursor.fetchall()
        return [row[0] for row in rows]


async def remove_favorite(telegram_id: int, coin: str) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "DELETE FROM favorites WHERE telegram_id = ? AND coin = ?",
            (telegram_id, coin),
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_favorite_assets(telegram_id: int) -> list[AssetDefinition]:
    symbols = set(await get_favorites(telegram_id))
    return [asset for asset in ASSET_REGISTRY if asset.symbol in symbols]
