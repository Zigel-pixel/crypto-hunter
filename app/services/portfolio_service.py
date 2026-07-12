from __future__ import annotations

from typing import Any
from io import BytesIO

import aiosqlite

from app.services.market_service import fetch_market_prices, format_price

DB_NAME = "crypto.db"


async def add_or_update_asset(
    telegram_id: int, coin: str, amount: float, average_buy_price: float
) -> None:
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """
            INSERT INTO portfolio (telegram_id, coin, amount, average_buy_price)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(telegram_id, coin) DO UPDATE SET
                amount = excluded.amount,
                average_buy_price = excluded.average_buy_price
            """,
            (telegram_id, coin, amount, average_buy_price),
        )
        await db.commit()


async def get_portfolio(telegram_id: int) -> list[dict[str, Any]]:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            """
            SELECT coin, amount, average_buy_price
            FROM portfolio WHERE telegram_id = ? ORDER BY coin
            """,
            (telegram_id,),
        )
        rows = await cursor.fetchall()
        return [
            {"coin": row[0], "amount": row[1], "average_buy_price": row[2]}
            for row in rows
        ]


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
    telegram_id: int, prices: dict[str, float]
) -> str:
    assets = await get_portfolio(telegram_id)
    if not assets:
        return "No assets in your portfolio."

    lines = ["💼 Your Portfolio", ""]
    total_value = 0.0
    total_cost = 0.0
    tracked_value = 0.0

    for asset in assets:
        coin = asset["coin"]
        amount = float(asset["amount"])
        price = prices.get(coin)
        if price is None:
            continue

        value = amount * price
        total_value += value
        buy_price_raw = asset.get("average_buy_price")
        if isinstance(buy_price_raw, (int, float)) and buy_price_raw > 0:
            cost = amount * float(buy_price_raw)
            profit = value - cost
            profit_percent = (profit / cost * 100) if cost else 0.0
            total_cost += cost
            tracked_value += value
            marker = "🟢" if profit >= 0 else "🔴"
            lines.append(f"• {coin}: {amount:g} × {format_price(float(price))}")
            lines.append(
                f"  {marker} P/L: {profit:+,.2f} USD ({profit_percent:+.2f}%)"
            )
        else:
            lines.append(f"• {coin}: {amount:g} = {format_price(value)} (ціна входу не задана)")

    lines.append("")
    lines.append(f"💰 Total Portfolio Value: {format_price(total_value)}")
    if total_cost > 0:
        total_profit = tracked_value - total_cost
        lines.append(f"📊 Total P/L: {total_profit:+,.2f} USD")
    return "\n".join(lines)


async def get_portfolio_text(telegram_id: int) -> str | None:
    """Build a portfolio response, or return ``None`` when prices are unavailable."""
    assets = await get_portfolio(telegram_id)
    if not assets:
        return "No assets in your portfolio."

    _, prices = await fetch_market_prices()
    if not prices:
        return None
    return await build_portfolio_text(telegram_id, prices)


async def get_portfolio_chart(telegram_id: int) -> bytes | None:
    assets = await get_portfolio(telegram_id)
    _, prices = await fetch_market_prices()
    if not assets or not prices:
        return None
    labels: list[str] = []
    profits: list[float] = []
    for asset in assets:
        symbol = str(asset["coin"])
        price = prices.get(symbol)
        buy_price = asset.get("average_buy_price")
        if price is None or not isinstance(buy_price, (int, float)) or buy_price <= 0:
            continue
        labels.append(symbol)
        profits.append(float(asset["amount"]) * (price - float(buy_price)))
    if not labels:
        return None

    from PIL import Image, ImageDraw

    width, height = 1000, 600
    image = Image.new("RGB", (width, height), "#111827")
    draw = ImageDraw.Draw(image)
    draw.text((50, 25), "Portfolio profit / loss (USD)", fill="#f9fafb")
    baseline = height // 2
    draw.line((50, baseline, width - 40, baseline), fill="#9ca3af", width=2)
    maximum = max((abs(value) for value in profits), default=1.0) or 1.0
    slot = (width - 100) / len(labels)
    for index, (label, profit) in enumerate(zip(labels, profits, strict=True)):
        x1 = 60 + index * slot
        x2 = x1 + slot * 0.65
        bar_height = abs(profit) / maximum * (height * 0.34)
        y1, y2 = (baseline - bar_height, baseline) if profit >= 0 else (baseline, baseline + bar_height)
        draw.rectangle((x1, y1, x2, y2), fill="#22c55e" if profit >= 0 else "#ef4444")
        draw.text((x1, height - 55), label, fill="#f9fafb")
        draw.text((x1, y1 - 18 if profit >= 0 else y2 + 5), f"{profit:+,.2f}", fill="#d1d5db")
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()
