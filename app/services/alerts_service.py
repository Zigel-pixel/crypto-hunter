from __future__ import annotations

from datetime import datetime, timezone
import aiosqlite

from app.models.alert import Alert

DB_NAME = "crypto.db"


async def create_alert(
    telegram_id: int, coin: str, condition: str, target_price: float
) -> None:
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """
            INSERT INTO alerts (telegram_id, coin, condition, target_price, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (telegram_id, coin, condition, target_price, created_at),
        )
        await db.commit()


async def get_alerts(telegram_id: int) -> list[dict[str, object]]:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            """
            SELECT id, coin, condition, target_price, created_at
            FROM alerts
            WHERE telegram_id = ?
            ORDER BY created_at DESC
            """,
            (telegram_id,),
        )
        rows = await cursor.fetchall()
        return [
            {
                "id": row[0],
                "coin": row[1],
                "condition": row[2],
                "target_price": row[3],
                "created_at": row[4],
            }
            for row in rows
        ]


async def get_all_alerts() -> list[Alert]:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            """
            SELECT id, telegram_id, coin, condition, target_price
            FROM alerts
            ORDER BY id
            """
        )
        rows = await cursor.fetchall()
    return [
        Alert(
            id=row[0],
            telegram_id=row[1],
            coin=row[2],
            condition=row[3],
            target_price=float(row[4]),
        )
        for row in rows
    ]


def is_alert_triggered(alert: Alert, current_price: float) -> bool:
    if alert.condition == ">":
        return current_price >= alert.target_price
    if alert.condition == "<":
        return current_price <= alert.target_price
    return False


async def delete_alert(alert_id: int, telegram_id: int) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "DELETE FROM alerts WHERE id = ? AND telegram_id = ?",
            (alert_id, telegram_id),
        )
        await db.commit()
        return cursor.rowcount > 0
