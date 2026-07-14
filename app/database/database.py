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
            CREATE TABLE IF NOT EXISTS wallet_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                address TEXT NOT NULL COLLATE NOCASE,
                address_family TEXT NOT NULL,
                label TEXT,
                created_at TEXT NOT NULL,
                last_refresh_at TEXT,
                UNIQUE(telegram_id, address_family, address)
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS wallet_networks (
                wallet_id INTEGER NOT NULL,
                network TEXT NOT NULL,
                PRIMARY KEY (wallet_id, network),
                FOREIGN KEY (wallet_id) REFERENCES wallet_profiles(id) ON DELETE CASCADE
            )
            """
        )

        cursor = await db.execute("PRAGMA table_info(users)")
        user_columns = {row[1] for row in await cursor.fetchall()}
        if "is_active" not in user_columns:
            await db.execute(
                "ALTER TABLE users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1"
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

        # Additive compatibility migration: retain legacy rows while making them
        # available to the address-centric model. Safe to run on every startup.
        await db.execute(
            """
            INSERT OR IGNORE INTO wallet_profiles
                (telegram_id, address, address_family, created_at)
            SELECT telegram_id, lower(address),
                   CASE WHEN network IN ('ethereum', 'bnb', 'polygon', 'arbitrum', 'base', 'optimism', 'avalanche')
                        THEN 'evm' ELSE network END,
                   created_at
            FROM wallets
            """
        )
        await db.execute(
            """
            INSERT OR IGNORE INTO wallet_networks (wallet_id, network)
            SELECT profile.id, legacy.network
            FROM wallets AS legacy
            JOIN wallet_profiles AS profile
              ON profile.telegram_id = legacy.telegram_id
             AND profile.address = legacy.address COLLATE NOCASE
            """
        )

        await db.commit()
