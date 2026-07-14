from __future__ import annotations

import re

from app.models.consultant import ConsultantIntent, ConsultantQuery

ASSET_ALIASES = {
    "BTC": ("btc", "bitcoin", "біткоїн", "биткоин"),
    "ETH": ("eth", "ethereum", "ефір", "эфир"),
    "SOL": ("sol", "solana", "солана"),
    "BNB": ("bnb", "binance coin"),
    "USDT": ("usdt", "tether"), "USDC": ("usdc", "usd coin"), "DAI": ("dai",),
}


def classify_query(value: str, language: str | None = None) -> ConsultantQuery:
    text = " ".join(value.strip().split())
    normalized = text.casefold()
    detected_language = language or ("Ukrainian" if re.search(r"[іїєґ]", normalized) else "English")
    assets = tuple(symbol for symbol, aliases in ASSET_ALIASES.items() if any(alias in normalized for alias in aliases))
    if any(word in normalized for word in ("stablecoin", "stable coin", "стейбл", "стабільн")) or any(x in assets for x in ("USDT", "USDC", "DAI")):
        intent = ConsultantIntent.STABLECOIN
    elif "defi" in normalized or "дефі" in normalized or "децентралізован" in normalized:
        intent = ConsultantIntent.DEFI
    elif any(word in normalized for word in (" vs ", " versus ", "compare", "порівняй", "краще")) and len(assets) >= 2:
        intent = ConsultantIntent.COMPARISON
    elif any(word in normalized for word in ("buy", "sell", "hold", "купувати", "продавати", "тримати", "входити")):
        intent = ConsultantIntent.TRADING_DECISION
    elif assets:
        intent = ConsultantIntent.ASSET_ANALYSIS
    elif any(word in normalized for word in ("market", "ринок", "огляд")):
        intent = ConsultantIntent.MARKET_OVERVIEW
    else:
        intent = ConsultantIntent.CONCEPT
    return ConsultantQuery(text, intent, assets, detected_language)
