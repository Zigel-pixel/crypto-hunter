# Crypto Hunter

Initial project structure for Crypto Hunter.
# Crypto Hunter

Telegram bot for cryptocurrency tracking.

## Features

- Live market prices
- Favorites
- Portfolio
- Alerts (WIP)
- News
- Settings
- Ethereum wallet portfolios with live balances

## Wallet Portfolio

Ethereum wallet data uses a provider manager with the following behavior:

- Alchemy is the primary provider and is retried once on failure.
- Etherscan is used automatically if Alchemy remains unavailable.
- A keyless public Ethereum RPC supplies native ETH balances when no API key is configured.
- Successful wallet responses are cached in memory for 60 seconds.
- Concurrent requests for the same wallet share one provider request.

Optionally configure a provider in `.env` for complete portfolio data:

```env
ALCHEMY_API_KEY=your_alchemy_api_key
ETHERSCAN_API_KEY=your_etherscan_api_key
```

API keys are optional. The public RPC fallback returns real native ETH only; it
cannot enumerate ERC-20 holdings or provide USD values.

## Stack

- Python 3.13
- aiogram 3
- SQLite
- aiohttp
- aiosqlite
- GitHub

## Run

python3 main.py
