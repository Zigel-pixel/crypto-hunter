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

        cursor = await db.execute("PRAGMA table_info(portfolio)")
        portfolio_columns = {row[1] for row in await cursor.fetchall()}
        if "average_buy_price" not in portfolio_columns:
            await db.execute("ALTER TABLE portfolio ADD COLUMN average_buy_price REAL")

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

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS wallets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                network TEXT NOT NULL,
                address TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(telegram_id, network, address)
            )
            """
        )

        await db.commit()
