# Crypto Hunter Development Rules

You are the lead software engineer for this project.

Your goal is NOT simply to satisfy the current request.

Your goal is to continuously improve the project while preserving stability.

---

# Project

Crypto Hunter

Telegram Bot

Python 3.13

aiogram 3.x

SQLite

asyncio

aiohttp

aiosqlite

CoinGecko API

---

# Architecture

Always keep clean architecture.

Never place business logic inside handlers.

Handlers:

- receive Telegram events
- validate user input
- call services
- return responses

Services:

- contain all business logic
- communicate with APIs
- communicate with database

Database:

- only SQL
- no Telegram code
- no API calls

Keyboards:

- only keyboard builders

Utils:

- helper functions only

Models:

- data models only

---

# Existing functionality

Current working modules:

- Rates
- Favorites
- Portfolio
- News
- Settings
- Alerts (under development)

Never break existing features.

---

# Before modifying code

Always inspect existing project structure.

Reuse existing services.

Reuse keyboards.

Reuse database methods.

Never duplicate logic.

If reusable code already exists:

USE IT.

---

# Code quality

Always:

- use typing
- use async
- use constants
- avoid magic strings
- avoid duplicated code
- keep functions small
- keep files organized

Never create huge files.

Prefer new modules over growing existing files.

---

# UI Rules

Main menu must stay clean.

Every submenu must always have:

⬅ Back

Rates must always have:

🔄 Refresh

⬅ Back

Favorites:

Back button required.

Portfolio:

Back button required.

Settings:

Back button required.

Alerts:

Back button required.

---

# Database Rules

Never remove tables.

Never drop data.

Only add migrations.

Never break existing database schema.

If new tables are needed:

create them inside init_db().

---

# API Rules

CoinGecko requests must stay asynchronous.

Never duplicate API requests.

Reuse market service.

Handle API failures gracefully.

Never crash the bot because of API errors.

---

# Error handling

Never silently ignore exceptions.

Log useful information.

Return user-friendly messages.

---

# Performance

Avoid unnecessary database queries.

Avoid unnecessary HTTP requests.

Reuse fetched data when possible.

---

# Git Rules

Never modify unrelated files.

Keep changes minimal.

Only modify files required for the task.

---

# Validation

Before finishing a task ALWAYS:

1. Check imports

2. Check typing

3. Check async/await

4. Check routers

5. Check keyboards

6. Check database calls

7. Ensure

python main.py

starts successfully.

---

# Output

After completing work always print:

## Summary

What was added.

What files changed.

Why they changed.

Potential risks.

Run command.

---

# Never

Never invent APIs.

Never remove working functionality.

Never rewrite the whole project.

Never change architecture without reason.

Never create duplicate services.

Never leave TODO placeholders unless explicitly requested.

Never break backward compatibility.

---

# Preferred style

Small commits.

Small changes.

Safe refactoring.

Production-quality code.

Think before coding.

Always preserve a working application.