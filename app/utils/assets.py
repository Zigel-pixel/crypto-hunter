from __future__ import annotations

COIN_IDS: dict[str, str] = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "BNB": "binancecoin",
    "USDT": "tether",
    "USDC": "usd-coin",
    "DAI": "dai",
    "XRP": "ripple",
    "ADA": "cardano",
    "DOGE": "dogecoin",
    "TRX": "tron",
    "TON": "the-open-network",
    "AVAX": "avalanche-2",
    "LINK": "chainlink",
    "DOT": "polkadot",
    "LTC": "litecoin",
}

ASSET_LABELS: dict[str, str] = {
    "BTC": "🟠 BTC",
    "ETH": "🔵 ETH",
    "SOL": "🟣 SOL",
    "BNB": "🟡 BNB",
    "USDT": "🟢 USDT",
    "USDC": "🔵 USDC",
    "DAI": "🟨 DAI",
    "XRP": "⚫ XRP",
    "ADA": "🔷 ADA",
    "DOGE": "🐕 DOGE",
    "TRX": "🔴 TRX",
    "TON": "💎 TON",
    "AVAX": "🔺 AVAX",
    "LINK": "🔗 LINK",
    "DOT": "⚪ DOT",
    "LTC": "⚙️ LTC",
}

SUPPORTED_SYMBOLS = tuple(COIN_IDS)
STABLECOINS = frozenset({"USDT", "USDC", "DAI"})

