# Crypto Hunter - Project Context

## Overview

Crypto Hunter is a Telegram bot built with Python 3.13 and aiogram 3.x.

The goal is to create a production-quality cryptocurrency assistant with a clean architecture.

The project must remain fully asynchronous.

---

## Tech Stack

- Python 3.13
- aiogram 3.x
- asyncio
- aiohttp
- SQLite
- aiosqlite
- CoinGecko API
- Git
- GitHub

---

## Architecture

Project structure:

app/
    handlers/
    keyboards/
    services/
    database/
    models/
    utils/

Rules:

- handlers only coordinate requests
- business logic lives in services
- SQLite access only through services/database
- keyboards are reusable
- never duplicate code
- keep modules small
- keep everything asynchronous

---

## Existing Features

✅ Main Menu

✅ Rates

- Bitcoin
- Ethereum
- Solana
- Refresh button

✅ Favorites

- Add coin
- My favorites
- Remove favorite
- SQLite storage

✅ Portfolio

- Add asset
- Remove asset
- Update asset
- View portfolio

✅ Settings UI

- Language
- Currency
- Timezone

✅ News placeholder

---

## Current Issues

- Alerts are not implemented yet.
- Settings logic is placeholder only.
- Rates screen should always provide a Back button.
- Portfolio uses CoinGecko prices.

---

## APIs

CoinGecko is the main data source.

Do not replace it unless explicitly requested.

---

## Coding Rules

Always preserve the project architecture.

Never rewrite working modules without reason.

Prefer improving existing code over replacing it.

Return complete modified files only.

Never break existing features.

Always keep backward compatibility.

---

## Git Workflow

Every completed feature should be committed.

Never leave the repository in a broken state.

Code must run with

python main.py

without additional manual fixes.

---

## Long-Term Vision

Crypto Hunter should become a full crypto assistant including:

- Alerts
- Portfolio analytics
- Charts
- Trending coins
- Fear & Greed Index
- Watchlist
- AI market analysis
- Multi-language support
- Background jobs
- Production deployment