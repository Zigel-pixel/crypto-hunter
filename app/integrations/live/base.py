from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol

from app.models.live_market import LiveQuote

QuoteCallback = Callable[[LiveQuote], Awaitable[None]]


class LiveMarketProvider(Protocol):
    async def run(self, on_quote: QuoteCallback) -> None: ...

