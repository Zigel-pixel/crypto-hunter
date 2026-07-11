# Crypto Hunter Roadmap

## Vision

Crypto Hunter is a professional Telegram bot for cryptocurrency investors.

The project should evolve into a production-quality application with clean architecture.

---

## Current Features

- Market rates
- Favorites
- SQLite database
- Modular handlers
- Modular services
- Telegram menus

---

## Planned Features

### High Priority

- Working Alerts
- Background price checker
- Portfolio tracking
- Settings persistence
- News integration

### Medium Priority

- Charts
- Trending coins
- Fear & Greed Index
- Top gainers
- Top losers
- Coin search

### Future

- Multi-language
- Multi-currency
- Admin panel
- PostgreSQL
- Docker
- Redis cache
- API layer
- Web dashboard

---

## Architecture Rules

Always improve existing architecture.

Never reduce code quality.

Never merge unrelated modules.

Every feature must have:

- handler
- service
- keyboard
- database functions if needed

Business logic belongs only inside services.

Handlers coordinate user requests only.

---

## Before Every Task

First inspect the current project.

Understand existing architecture.

Modify only what is necessary.

Return only changed files.

Never rewrite the whole project unless explicitly requested.

---

## Git

Every completed feature should keep the project runnable.

Never leave broken imports.

Never leave dead code.

Never remove existing functionality.