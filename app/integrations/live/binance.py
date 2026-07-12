from __future__ import annotations

import asyncio
import json
import logging
import ssl
from datetime import datetime, timezone
from typing import Any

import aiohttp
import certifi

from app.integrations.live.base import QuoteCallback
from app.models.live_market import LiveQuote

STREAM_SYMBOLS = ("btcusdt", "ethusdt", "solusdt", "bnbusdt")
STREAM_URL = "wss://stream.binance.com:9443/stream?streams=" + "/".join(
    f"{symbol}@miniTicker" for symbol in STREAM_SYMBOLS
)
SOURCE_NAME = "Binance WebSocket"
MAX_BACKOFF_SECONDS = 30

logger = logging.getLogger(__name__)


class BinanceLiveProvider:
    async def run(self, on_quote: QuoteCallback) -> None:
        backoff = 1
        while True:
            try:
                timeout = aiohttp.ClientTimeout(total=None, sock_connect=15)
                ssl_context = ssl.create_default_context(cafile=certifi.where())
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.ws_connect(
                        STREAM_URL, heartbeat=20, ssl=ssl_context
                    ) as socket:
                        logger.info("Connected to Binance live market stream")
                        backoff = 1
                        async for message in socket:
                            if message.type == aiohttp.WSMsgType.TEXT:
                                quote = _parse_message(message.data)
                                if quote is not None:
                                    await on_quote(quote)
                            elif message.type in {
                                aiohttp.WSMsgType.CLOSED,
                                aiohttp.WSMsgType.ERROR,
                            }:
                                break
            except asyncio.CancelledError:
                raise
            except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
                logger.warning(
                    "Binance live stream failed; reconnecting in %ss: %s", backoff, exc
                )
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, MAX_BACKOFF_SECONDS)


def _parse_message(payload: str) -> LiveQuote | None:
    try:
        envelope: Any = json.loads(payload)
        data = envelope.get("data") if isinstance(envelope, dict) else None
        symbol = data.get("s") if isinstance(data, dict) else None
        price = data.get("c") if isinstance(data, dict) else None
        event_time = data.get("E") if isinstance(data, dict) else None
        if not isinstance(symbol, str) or not isinstance(price, str):
            return None
        updated_at = (
            datetime.fromtimestamp(event_time / 1000, timezone.utc)
            if isinstance(event_time, (int, float))
            else datetime.now(timezone.utc)
        )
        return LiveQuote(symbol.removesuffix("USDT"), float(price), updated_at, SOURCE_NAME)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
