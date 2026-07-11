from __future__ import annotations

import ssl
import traceback
from datetime import datetime, timezone
from typing import Any

import aiohttp
import certifi

COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"


def format_price(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"${value:,.2f}"


def format_market_cap(value: float | None) -> str:
    if value is None:
        return "N/A"

    if value >= 1_000_000_000_000:
        return f"${value / 1_000_000_000_000:,.2f}T"
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:,.2f}B"
    if value >= 1_000_000:
        return f"${value / 1_000_000:,.2f}M"
    return f"${value:,.0f}"


def format_percent(value: float | None) -> str:
    if value is None:
        return "N/A"

    sign = "+" if value >= 0 else ""
    color = "🟢" if value >= 0 else "🔴"
    return f"{color} {sign}{value:.2f}%"


async def fetch_market_prices() -> tuple[str | None, dict[str, dict[str, Any]] | None]:
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    params = {
        "ids": "bitcoin,ethereum,solana",
        "vs_currencies": "usd",
        "include_24hr_change": "true",
        "include_market_cap": "true",
        "include_24hr_vol": "true",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                COINGECKO_URL,
                params=params,
                timeout=10,
                ssl=ssl_context,
            ) as response:
                response.raise_for_status()
                data: dict[str, Any] = await response.json()
    except Exception as exc:
        print("Failed to fetch market prices:", exc)
        traceback.print_exc()
        return None, None

    parsed = {
        "BTC": {
            "price": data.get("bitcoin", {}).get("usd"),
            "change_24h": data.get("bitcoin", {}).get("usd_24h_change"),
            "market_cap": data.get("bitcoin", {}).get("usd_market_cap"),
            "volume_24h": data.get("bitcoin", {}).get("usd_24h_vol"),
        },
        "ETH": {
            "price": data.get("ethereum", {}).get("usd"),
            "change_24h": data.get("ethereum", {}).get("usd_24h_change"),
            "market_cap": data.get("ethereum", {}).get("usd_market_cap"),
            "volume_24h": data.get("ethereum", {}).get("usd_24h_vol"),
        },
        "SOL": {
            "price": data.get("solana", {}).get("usd"),
            "change_24h": data.get("solana", {}).get("usd_24h_change"),
            "market_cap": data.get("solana", {}).get("usd_market_cap"),
            "volume_24h": data.get("solana", {}).get("usd_24h_vol"),
        },
    }

    if any(coin_data.get("price") is None for coin_data in parsed.values()):
        return None, None

    return datetime.now(timezone.utc).strftime("%H:%M UTC"), parsed
