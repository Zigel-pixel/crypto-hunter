from __future__ import annotations

import ssl
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import aiohttp
import certifi

COINGECKO_MARKETS_URL = "https://api.coingecko.com/api/v3/coins/markets"


@dataclass(frozen=True)
class CoinSnapshot:
    id: str
    name: str
    symbol: str
    price: float | None
    change_24h: float | None
    market_cap: float | None
    volume_24h: float | None
    market_rank: int | None
    circulating_supply: float | None
    ath: float | None
    ath_change_percentage: float | None
    updated_at: str


def format_price(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"${value:,.2f}"


def format_compact_currency(value: float | None) -> str:
    if value is None:
        return "N/A"

    if value >= 1_000_000_000_000:
        return f"${value / 1_000_000_000_000:,.2f}T"
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:,.2f}B"
    if value >= 1_000_000:
        return f"${value / 1_000_000:,.2f}M"
    if value >= 1_000:
        return f"${value / 1_000:,.2f}K"
    return f"${value:,.0f}"


def format_compact_number(value: float | None) -> str:
    if value is None:
        return "N/A"

    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:,.2f}B"
    if value >= 1_000_000:
        return f"{value / 1_000_000:,.2f}M"
    if value >= 1_000:
        return f"{value / 1_000:,.2f}K"
    return f"{value:,.0f}"


def format_supply(value: float | None, symbol: str) -> str:
    if value is None:
        return "N/A"
    return f"{format_compact_number(value)} {symbol.upper()}"


def format_percent(value: float | None) -> str:
    if value is None:
        return "N/A"

    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.2f}%"


def _format_updated_at(value: Any) -> str:
    if not value:
        return "N/A"

    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return "N/A"
    elif isinstance(value, (int, float)):
        parsed = datetime.fromtimestamp(int(value), timezone.utc)
    else:
        return "N/A"

    return parsed.astimezone(timezone.utc).strftime("%H:%M UTC")


async def fetch_market_snapshots(
    coin_ids: tuple[str, ...] = ("bitcoin", "ethereum", "solana"),
) -> tuple[str | None, dict[str, CoinSnapshot] | None]:
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    params = {
        "vs_currency": "usd",
        "ids": ",".join(coin_ids),
        "order": "market_cap_desc",
        "per_page": 100,
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "24h",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                COINGECKO_MARKETS_URL,
                params=params,
                timeout=10,
                ssl=ssl_context,
            ) as response:
                response.raise_for_status()
                data: list[dict[str, Any]] = await response.json()
    except Exception as exc:
        print("Failed to fetch market snapshots:", exc)
        traceback.print_exc()
        return None, None

    parsed: dict[str, CoinSnapshot] = {}
    for item in data:
        coin_id = item.get("id")
        if not isinstance(coin_id, str):
            continue
        parsed[coin_id] = CoinSnapshot(
            id=coin_id,
            name=str(item.get("name") or coin_id),
            symbol=str(item.get("symbol") or coin_id.upper()),
            price=item.get("current_price"),
            change_24h=item.get("price_change_percentage_24h"),
            market_cap=item.get("market_cap"),
            volume_24h=item.get("total_volume"),
            market_rank=item.get("market_cap_rank"),
            circulating_supply=item.get("circulating_supply"),
            ath=item.get("ath"),
            ath_change_percentage=item.get("ath_change_percentage"),
            updated_at=_format_updated_at(item.get("last_updated")),
        )

    if not parsed:
        return None, None

    return parsed[next(iter(parsed))].updated_at, parsed


async def fetch_market_prices() -> tuple[str | None, dict[str, float] | None]:
    updated_at, snapshots = await fetch_market_snapshots()

    if not updated_at or not snapshots:
        return None, None

    prices = {}

    mapping = {
        "bitcoin": "BTC",
        "ethereum": "ETH",
        "solana": "SOL",
    }

    for coin_id, symbol in mapping.items():
        snapshot = snapshots.get(coin_id)
        if snapshot and snapshot.price is not None:
            prices[symbol] = snapshot.price

    return updated_at, prices
