from __future__ import annotations

from typing import List


async def get_news() -> List[str]:
    return ["News service placeholder."]
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
        if coin_id in snapshots:
            prices[symbol] = snapshots[coin_id].price

    return updated_at, prices