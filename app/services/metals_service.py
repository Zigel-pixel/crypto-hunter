from __future__ import annotations

import logging
import ssl
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import aiohttp
import certifi

GOLD_API_URL = "https://api.gold-api.com/price/{symbol}"
HISTORY_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
REQUEST_TIMEOUT_SECONDS = 15
METALS: dict[str, str] = {
    "XAU": "🥇 Gold",
    "XAG": "🥈 Silver",
    "XPT": "⚪ Platinum",
    "XPD": "🔘 Palladium",
}
HISTORY_SYMBOLS = {"XAU": "GC=F", "XAG": "SI=F", "XPT": "PL=F", "XPD": "PA=F"}

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MetalSnapshot:
    symbol: str
    name: str
    price: float
    updated_at: datetime


async def fetch_metal(symbol: str) -> MetalSnapshot | None:
    if symbol not in METALS:
        return None
    data = await _get_json(GOLD_API_URL.format(symbol=symbol))
    price = data.get("price") if isinstance(data, dict) else None
    if not isinstance(price, (int, float)):
        return None
    return MetalSnapshot(symbol, METALS[symbol], float(price), datetime.now(timezone.utc))


async def fetch_metal_history(symbol: str) -> list[tuple[datetime, float]]:
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
        logger.warning("Metal history request failed: %s", exc)
        return []
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
        logger.warning("Metal history returned invalid data: %s", exc)
        return []
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
        logger.warning("Metal price request failed: %s", exc)
        return None
