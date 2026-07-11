from __future__ import annotations

from typing import Any, List

import aiosqlite

from app.services.market_service import format_price

DB_NAME = "crypto.db"


async def add_or_update_asset(telegram_id: int, coin: str, amount: float) -> None:
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """
            INSERT INTO portfolio (telegram_id, coin, amount)
            VALUES (?, ?, ?)
            ON CONFLICT(telegram_id, coin) DO UPDATE SET amount = excluded.amount
            """,
            (telegram_id, coin, amount),
        )
        await db.commit()


async def get_portfolio(telegram_id: int) -> List[dict[str, Any]]:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT coin, amount FROM portfolio WHERE telegram_id = ? ORDER BY coin",
            (telegram_id,),
        )
        rows = await cursor.fetchall()
        return [{"coin": row[0], "amount": row[1]} for row in rows]


async def update_asset_amount(telegram_id: int, coin: str, amount: float) -> None:
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE portfolio SET amount = ? WHERE telegram_id = ? AND coin = ?",
            (amount, telegram_id, coin),
        )
        await db.commit()


async def delete_asset(telegram_id: int, coin: str) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "DELETE FROM portfolio WHERE telegram_id = ? AND coin = ?",
            (telegram_id, coin),
        )
        await db.commit()
        return cursor.rowcount > 0


async def build_portfolio_text(
    telegram_id: int, prices: dict[str, dict[str, Any]]
) -> str:
    assets = await get_portfolio(telegram_id)
    if not assets:
        return "No assets in your portfolio."

    lines = ["💼 Your Portfolio", ""]
    total_value = 0.0

    for asset in assets:
        coin = asset["coin"]
        amount = float(asset["amount"])
        price = prices.get(coin, {}).get("price")
        if price is None:
            continue

        value = amount * float(price)
        total_value += value
        lines.append(
            f"• {coin}: {amount} @ {format_price(float(price))} = {format_price(value)}"
        )

    lines.append("")
    lines.append(f"💰 Total Portfolio Value: {format_price(total_value)}")
    return "\n".join(lines)
