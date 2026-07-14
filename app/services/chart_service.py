from __future__ import annotations

from datetime import datetime
from io import BytesIO

from app.services.market_service import fetch_price_history

TIMEFRAME_SECONDS = {"15m": 900, "1h": 3600, "4h": 14400, "24h": 86400, "7d": 604800}


async def build_crypto_chart(coin_id: str, symbol: str) -> bytes | None:
    history = await fetch_price_history(coin_id)
    if len(history) < 2:
        return None
    return render_chart(history, f"{symbol}/USD — 24 hours")


async def build_timeframe_chart(coin_id: str, symbol: str, timeframe: str) -> tuple[bytes, list[tuple[datetime, float]]] | None:
    seconds = TIMEFRAME_SECONDS.get(timeframe)
    if seconds is None:
        raise ValueError("Unsupported chart timeframe")
    history = await fetch_price_history(coin_id, days=7 if timeframe == "7d" else 1)
    if not history:
        return None
    cutoff = history[-1][0].timestamp() - seconds
    points = [point for point in history if point[0].timestamp() >= cutoff]
    if len(points) < 2:
        return None
    return render_chart(points, f"{symbol}/USD — {timeframe}"), points


def render_chart(points: list[tuple[datetime, float]], title: str) -> bytes:
    prices = [point[1] for point in points]
    from PIL import Image, ImageDraw

    width, height = 1200, 650
    left, top, right, bottom = 90, 70, 40, 80
    image = Image.new("RGB", (width, height), "#111827")
    draw = ImageDraw.Draw(image)
    draw.text((left, 24), title, fill="#f9fafb")
    minimum, maximum = min(prices), max(prices)
    span = maximum - minimum or 1.0
    plot_width = width - left - right
    plot_height = height - top - bottom
    for index in range(5):
        y = top + plot_height * index / 4
        value = maximum - span * index / 4
        draw.line((left, y, width - right, y), fill="#374151", width=1)
        draw.text((8, y - 7), f"${value:,.2f}", fill="#d1d5db")
    coordinates = [
        (
            left + plot_width * index / max(1, len(prices) - 1),
            top + (maximum - price) / span * plot_height,
        )
        for index, price in enumerate(prices)
    ]
    color = "#22c55e" if prices[-1] >= prices[0] else "#ef4444"
    draw.line(coordinates, fill=color, width=4, joint="curve")
    draw.text((left, height - 52), points[0][0].strftime("%d.%m %H:%M"), fill="#d1d5db")
    draw.text((width - 145, height - 52), points[-1][0].strftime("%d.%m %H:%M"), fill="#d1d5db")
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()
