"""Service-facing facade for CoinGecko market data.

The concrete HTTP implementation belongs to ``app.integrations.coingecko`` so it
can be replaced without changing service or handler contracts.
"""

from app.integrations.coingecko import (
    CoinSnapshot,
    fetch_market_prices,
    fetch_price_history,
    fetch_market_snapshots,
    format_compact_currency,
    format_compact_number,
    format_percent,
    format_price,
    format_supply,
)

__all__ = [
    "CoinSnapshot",
    "fetch_market_prices",
    "fetch_price_history",
    "fetch_market_snapshots",
    "format_compact_currency",
    "format_compact_number",
    "format_percent",
    "format_price",
    "format_supply",
]
