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

- Moralis is the primary provider and is retried once on failure.
- Alchemy is used automatically if Moralis remains unavailable.
- Successful wallet responses are cached in memory for 60 seconds.
- Concurrent requests for the same wallet share one provider request.

Configure at least one provider in `.env`:

```env
MORALIS_API_KEY=your_moralis_api_key
ALCHEMY_API_KEY=your_alchemy_api_key
```

## Stack

- Python 3.13
- aiogram 3
- SQLite
- aiohttp
- aiosqlite
- GitHub

## Run

python3 main.py
