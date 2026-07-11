from __future__ import annotations

import aiosqlite

DB_NAME = "crypto.db"


async def init_db() -> None:
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS favorites (
                telegram_id INTEGER,
                coin TEXT,
                PRIMARY KEY (telegram_id, coin)
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                coin TEXT NOT NULL,
                condition TEXT NOT NULL,
                target_price REAL NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS portfolio (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                coin TEXT NOT NULL,
                amount REAL NOT NULL,
                UNIQUE(telegram_id, coin)
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                telegram_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                value TEXT NOT NULL,
                PRIMARY KEY (telegram_id, category)
            )
            """
        )

        await db.commit()
