from __future__ import annotations

from app.models.asset import AssetDefinition

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

ASSET_NAMES: dict[str, str] = {
    "BTC": "Bitcoin", "ETH": "Ethereum", "SOL": "Solana", "BNB": "BNB",
    "USDT": "Tether", "USDC": "USD Coin", "DAI": "Dai", "XRP": "XRP",
    "ADA": "Cardano", "DOGE": "Dogecoin", "TRX": "TRON", "TON": "Toncoin",
    "AVAX": "Avalanche", "LINK": "Chainlink", "DOT": "Polkadot", "LTC": "Litecoin",
}

ASSET_REGISTRY: tuple[AssetDefinition, ...] = tuple(
    AssetDefinition(symbol, ASSET_NAMES[symbol], provider_id, ASSET_LABELS[symbol])
    for symbol, provider_id in COIN_IDS.items()
)
