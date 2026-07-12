from __future__ import annotations

import logging
import ssl
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import aiohttp
import certifi

from app.utils.assets import COIN_IDS

COINGECKO_MARKETS_URL = "https://api.coingecko.com/api/v3/coins/markets"
COINGECKO_CHART_URL = "https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
DEFAULT_COIN_IDS: tuple[str, ...] = tuple(COIN_IDS.values())
COIN_SYMBOLS: dict[str, str] = {coin_id: symbol for symbol, coin_id in COIN_IDS.items()}
REQUEST_TIMEOUT_SECONDS = 10

logger = logging.getLogger(__name__)


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
    return "N/A" if value is None else f"${value:,.2f}"


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
    return "N/A" if value is None else f"{format_compact_number(value)} {symbol.upper()}"


def format_percent(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{'+' if value >= 0 else ''}{value:.2f}%"


def _format_updated_at(value: Any) -> str:
    if not value:
        return "N/A"
    try:
        if isinstance(value, str):
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        elif isinstance(value, (int, float)):
            parsed = datetime.fromtimestamp(value, timezone.utc)
        else:
            return "N/A"
    except (OSError, OverflowError, ValueError):
        return "N/A"
    return parsed.astimezone(timezone.utc).strftime("%H:%M UTC")


def _optional_float(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


async def fetch_market_snapshots(
    coin_ids: tuple[str, ...] = DEFAULT_COIN_IDS,
) -> tuple[str | None, dict[str, CoinSnapshot] | None]:
    params = {
        "vs_currency": "usd",
        "ids": ",".join(coin_ids),
        "order": "market_cap_desc",
        "per_page": 100,
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "24h",
    }
    ssl_context = ssl.create_default_context(cafile=certifi.where())

    try:
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                COINGECKO_MARKETS_URL, params=params, ssl=ssl_context
            ) as response:
                response.raise_for_status()
                data: list[dict[str, Any]] = await response.json()
    except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
        logger.warning("CoinGecko market request failed: %s", exc)
        return None, None

    snapshots: dict[str, CoinSnapshot] = {}
    for item in data:
        coin_id = item.get("id")
        if not isinstance(coin_id, str):
            continue
        rank = item.get("market_cap_rank")
        snapshots[coin_id] = CoinSnapshot(
            id=coin_id,
            name=str(item.get("name") or coin_id),
            symbol=str(item.get("symbol") or coin_id.upper()),
            price=_optional_float(item.get("current_price")),
            change_24h=_optional_float(item.get("price_change_percentage_24h")),
            market_cap=_optional_float(item.get("market_cap")),
            volume_24h=_optional_float(item.get("total_volume")),
            market_rank=rank if isinstance(rank, int) else None,
            circulating_supply=_optional_float(item.get("circulating_supply")),
            ath=_optional_float(item.get("ath")),
            ath_change_percentage=_optional_float(item.get("ath_change_percentage")),
            updated_at=_format_updated_at(item.get("last_updated")),
        )

    if not snapshots:
        logger.warning("CoinGecko market request returned no supported snapshots")
        return None, None
    return next(iter(snapshots.values())).updated_at, snapshots


async def fetch_market_prices() -> tuple[str | None, dict[str, float] | None]:
    updated_at, snapshots = await fetch_market_snapshots()
    if not updated_at or not snapshots:
        return None, None

    prices = {
        symbol: snapshot.price
        for coin_id, symbol in COIN_SYMBOLS.items()
        if (snapshot := snapshots.get(coin_id)) is not None and snapshot.price is not None
    }
    return (updated_at, prices) if prices else (None, None)


async def fetch_price_history(coin_id: str, days: int = 1) -> list[tuple[datetime, float]]:
    """Fetch real USD price points for a chart."""
    params = {"vs_currency": "usd", "days": str(days)}
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    try:
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                COINGECKO_CHART_URL.format(coin_id=coin_id),
                params=params,
                ssl=ssl_context,
            ) as response:
                response.raise_for_status()
                data: Any = await response.json()
    except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
        logger.warning("CoinGecko chart request failed: %s", exc)
        return []
    prices = data.get("prices") if isinstance(data, dict) else None
    if not isinstance(prices, list):
        return []
    history: list[tuple[datetime, float]] = []
    for point in prices:
        if (
            isinstance(point, list)
            and len(point) >= 2
            and isinstance(point[0], (int, float))
            and isinstance(point[1], (int, float))
        ):
            history.append(
                (datetime.fromtimestamp(point[0] / 1000, timezone.utc), float(point[1]))
            )
    return history
