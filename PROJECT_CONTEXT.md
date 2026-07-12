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

## Stability Fixes (2026-07-12)

- Rates callback navigation now checks the Telegram message type before editing:
  text messages use `edit_text`, media captions use `edit_caption`, and messages
  without editable text send a replacement message. Related
  `TelegramBadRequest` failures fall back safely.
- Rates chart refresh edits an existing photo when possible instead of always
  creating another chart message.
- CoinGecko market snapshots and chart histories use a shared in-memory TTL
  cache. Identical concurrent requests share one provider task. A recent stale
  real response is used for up to 15 minutes when CoinGecko returns HTTP 429,
  times out, or is unavailable.
- Local polling uses a macOS/POSIX advisory lock at `.crypto-hunter.lock`.
  A second local process exits immediately and reports the PID that owns the
  lock. The OS releases the lock on normal exit and process crashes.

### Remaining Manual Telegram Tests

- Navigate Rates from a text menu to a photo chart and back, then refresh both
  views and confirm that no duplicate messages or `TelegramBadRequest` errors
  appear.
- Confirm caption editing behavior with charts previously sent by the bot.
- Confirm the user-facing stale-data behavior during an actual CoinGecko 429.

---

## APIs

CoinGecko is the main data source.

Do not replace it unless explicitly requested.

---

## Phase 1 Market Utility (2026-07-12)

### Snapshot Mode

- CoinGecko supplies regular crypto views, Assets, Portfolio, and consultant
  context through the shared market-service facade.
- Snapshot and chart requests use a 60-second in-memory TTL cache, concurrent
  request coalescing, and a 15-minute stale-real-data fallback during HTTP 429,
  timeouts, or provider outages. No value is fabricated.
- All configured CoinGecko IDs were validated against a live response. Missing
  assets are marked unavailable without breaking the rest of Rates.
- Gold and silver spot prices use the free keyless Gold API endpoint. Responses
  have the same TTL/stale behavior and display provider and update time.

### Live Mode

- Binance's official public combined WebSocket mini-ticker stream supplies
  BTC/USDT, ETH/USDT, SOL/USDT, and BNB/USDT.
- Telegram rendering is throttled to 2.5 seconds and skips edits when the
  rounded displayed prices have not changed.
- One task is allowed per chat. Start, Stop, Rates Back, other callbacks, other
  messages, and bot shutdown stop tasks safely. WebSocket failures reconnect
  with exponential backoff capped at 30 seconds.

### Assets

- `🔎 Assets` and `/assets` open a dedicated section backed by the central asset
  registry.
- Users can browse, search by ticker/name, open an asset page, refresh it, and
  navigate back safely.
- Pages show only provider fields that exist: current price, 24-hour change,
  high/low, market cap, volume, source, and update time. Missing data displays
  as unavailable rather than using fake values.

### Architecture Seams Preserved

- `market_service` remains the snapshot provider facade.
- `LiveMarketProvider` isolates future WebSocket providers from task handling.
- `ASSET_REGISTRY` is the single mapping source for symbols and CoinGecko IDs.
- Existing wallet fetcher/validator registries remain the extension point for
  future networks.
- The consultant remains service-based and no paid AI provider, payment, or
  subscription logic is included in Phase 1.

### Phase 1 Manual Telegram Tests Remaining

- Exercise Start Live, Stop Live, Back, and switching to another main-menu
  section on a real Telegram client for several minutes.
- Confirm message edit pacing and duplicate suppression under rapid live ticks.
- Browse and search Assets, including unavailable-provider behavior during a
  forced CoinGecko outage.
- Navigate text Rates → photo chart → Rates menu → main menu and verify caption
  edits on messages originally sent by Telegram.

---

## Coding Rules

Always preserve the project architecture.

---

## User Utility Milestone (2026-07-12)

### Rate Freshness

- All snapshot consumers continue to use the shared CoinGecko integration via
  `market_service` (Rates, Watchlist, Portfolio, consultant, and Alerts).
- Fresh cache TTL is 15 seconds. A successful real response may be reused as a
  stale fallback for 15 minutes during HTTP 429, timeout, malformed response,
  or temporary provider failure.
- Manual refresh bypasses the normal TTL but has a three-second per-resource
  cooldown. Concurrent requests still join one provider task.
- Rates and Watchlist distinguish fresh timestamps from stale cached timestamps.
  UTC is the fallback; a saved IANA timezone is used on user-specific screens.

### Watchlist

- The existing `favorites` table remains the only persistence mechanism and
  `PRIMARY KEY (telegram_id, coin)` still prevents duplicates.
- The main UI name is `⭐ Watchlist`; legacy Favorites labels remain accepted.
- Overview displays name, ticker, price, 24-hour change, direction, provider,
  and update time. It supports inline refresh, add, remove, details, and Back.
- Add searches the supported central asset registry by ticker or name and shows
  a selection for multiple matches. Detail pages omit fields unavailable from
  the provider rather than displaying fake zeroes.

### Per-user Start / Restart / Stop

- `start.py` is the single owner of `/start`, `/restart`, `/stop`, and their
  clickable reply-keyboard controls.
- Start registers/reactivates idempotently, clears FSM state, stops the user's
  Live task, and restores the main menu.
- Restart resets only temporary interaction/FSM/Live state and preserves all
  database-backed data.
- Stop sets only that user's `users.is_active` to `0`, clears temporary state,
  and shows a minimal Start keyboard. A session middleware blocks ordinary
  messages and answers old callbacks while stopped; Start always bypasses it.
- Migration: `users.is_active INTEGER NOT NULL DEFAULT 1` is added through
  `init_db()` without deleting or rewriting existing rows.

### Validation for This Milestone

- `.venv/bin/python -m compileall -q app tests main.py`
- `.venv/bin/python -m unittest discover -s tests -v` — 17 tests passed.
- Duplicate command audit confirmed one `/start`, one `/restart`, and one
  `/stop` owner.

### Manual Telegram Checks Remaining

- Repeatedly refresh Rates and Watchlist and confirm the callback immediately
  shows `Updating…`, the existing message updates, and the cooldown prevents a
  request storm.
- Verify stale timestamp wording during a real or simulated CoinGecko outage.
- Test Watchlist add/search/duplicate/remove/detail/back on mobile Telegram.
- Test Start → Stop → old inline callback → Start, and confirm a second user is
  unaffected.

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
