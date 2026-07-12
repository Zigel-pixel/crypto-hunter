from __future__ import annotations

import logging
import ssl
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import aiohttp
import certifi

from app.integrations.coingecko.cache import AsyncTTLCache

GOLD_API_URL = "https://api.gold-api.com/price/{symbol}"
HISTORY_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
REQUEST_TIMEOUT_SECONDS = 15
METALS: dict[str, str] = {
    "XAU": "🥇 Gold",
    "XAG": "🥈 Silver",
}
HISTORY_SYMBOLS = {"XAU": "GC=F", "XAG": "SI=F"}
CACHE_TTL_SECONDS = 60
STALE_CACHE_TTL_SECONDS = 15 * 60

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MetalSnapshot:
    symbol: str
    name: str
    price: float
    updated_at: datetime
    provider: str = "Gold API"


class MetalProviderError(RuntimeError):
    """Raised when a metals provider cannot return valid real data."""


_metal_cache: AsyncTTLCache[MetalSnapshot] = AsyncTTLCache(
    CACHE_TTL_SECONDS, STALE_CACHE_TTL_SECONDS, logger, "Gold API"
)
_history_cache: AsyncTTLCache[list[tuple[datetime, float]]] = AsyncTTLCache(
    5 * 60, STALE_CACHE_TTL_SECONDS, logger, "Metal history"
)


async def fetch_metal(symbol: str) -> MetalSnapshot | None:
    if symbol not in METALS:
        return None
    try:
        return await _metal_cache.get(symbol, lambda: _fetch_metal_uncached(symbol))
    except MetalProviderError:
        return None


async def _fetch_metal_uncached(symbol: str) -> MetalSnapshot:
    data = await _get_json(GOLD_API_URL.format(symbol=symbol))
    price = data.get("price") if isinstance(data, dict) else None
    if not isinstance(price, (int, float)):
        raise MetalProviderError("invalid price response")
    updated_at = _parse_updated_at(data.get("updatedAt"))
    return MetalSnapshot(symbol, METALS[symbol], float(price), updated_at)


def _parse_updated_at(value: Any) -> datetime:
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
                timezone.utc
            )
        except ValueError:
            logger.debug("Gold API returned an invalid update timestamp: %s", value)
    return datetime.now(timezone.utc)


async def fetch_metal_history(symbol: str) -> list[tuple[datetime, float]]:
    try:
        return await _history_cache.get(
            symbol, lambda: _fetch_metal_history_uncached(symbol)
        )
    except MetalProviderError:
        return []


async def _fetch_metal_history_uncached(symbol: str) -> list[tuple[datetime, float]]:
    history_symbol = HISTORY_SYMBOLS.get(symbol)
    if history_symbol is None:
        return []
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                HISTORY_URL.format(symbol=history_symbol),
                params={"range": "1mo", "interval": "1d"},
                ssl=ssl_context,
            ) as response:
                response.raise_for_status()
                payload: Any = await response.json()
    except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
        raise MetalProviderError(str(exc)) from exc
    try:
        result = payload["chart"]["result"][0]
        timestamps = result["timestamp"]
        closes = result["indicators"]["quote"][0]["close"]
        points = [
            (datetime.fromtimestamp(timestamp, timezone.utc), float(close))
            for timestamp, close in zip(timestamps, closes, strict=True)
            if close is not None
        ]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise MetalProviderError("invalid history response") from exc
    if not points:
        raise MetalProviderError("history response contained no prices")
    return points


async def _get_json(url: str) -> Any:
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, ssl=ssl_context) as response:
                response.raise_for_status()
                return await response.json()
    except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
        raise MetalProviderError(str(exc)) from exc
