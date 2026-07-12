Read AGENTS.md and PROJECT_CONTEXT.md first.

You are the lead software engineer and product architect for Crypto Hunter.

Your mission is not only to write code but to build Crypto Hunter into a high-quality Telegram product.

==================================================
PRODUCT VISION
==================================================

Crypto Hunter serves two audiences.

1. Beginners

The bot should help people enter crypto safely.

Users should be able to ask:

- what is Bitcoin
- what is USDT
- what is ERC20
- what is TRC20
- what network should I use
- how do I buy crypto
- how do I transfer crypto
- what wallet should I choose
- what are the risks
- how to avoid scams

Responses should be educational, simple and practical.

2. Experienced users

Crypto Hunter should become a utility they open many times every day.

They should quickly access:

- live prices
- portfolio
- watchlist
- wallet balances
- alerts
- market overview
- AI analysis

The bot should be fast.

==================================================
LONG TERM ROADMAP
==================================================

Phase 1
Product stability

Phase 2
Reliable market data

Phase 3
Wallet scanner

Phase 4
Portfolio

Phase 5
AI assistant

Phase 6
Alerts

Phase 7
Premium AI

Phase 8
Deployment

Never try to implement multiple roadmap phases randomly.

==================================================
GENERAL RULES
==================================================

Read the repository before changing code.

Preserve existing working functionality.

Prefer small safe improvements.

Never invent API results.

Never fabricate market prices.

Never expose secrets.

Never delete files unless proven unused.

Never claim production readiness unless every major feature is fully implemented and tested.

Update PROJECT_CONTEXT.md whenever project state changes.

Do not commit or push.

==================================================
STABILITY
==================================================

Fix and prevent:

TelegramBadRequest

CoinGecko HTTP 429

duplicate polling

unsafe edit_text

broken callback navigation

dangling background tasks

duplicate Live tasks

Handle failures gracefully.

==================================================
USER SESSION
==================================================

Implement:

/start

/restart

/stop

Behavior:

/start

- initialize user
- restore clean menu
- preserve stored data

/restart

- reset only that user's interaction
- clear FSM
- stop that user's Live Market
- stop pending conversations
- preserve portfolio
- preserve wallets
- preserve watchlist
- preserve alerts

/stop

- stop only the current interaction
- preserve user data
- allow continuing with /start

These commands must never restart or stop the bot process.

==================================================
MARKET DATA
==================================================

Create two modes.

Snapshot mode

Used for:

- rates
- portfolio
- watchlist
- consultant
- alerts

Requirements:

TTL cache

batch requests

provider fallback

stale cache fallback

request deduplication

timestamps

provider names

Live mode

Use WebSockets.

Never poll CoinGecko every second.

Support:

BTC

ETH

SOL

BNB

Future:

XRP

DOGE

ADA

LINK

TRX

Features:

Start Live

Stop Live

Back

single task per user

automatic cleanup

reconnect

rate limit friendly

==================================================
RATES
==================================================

Audit every displayed asset.

Verify:

mapping

provider IDs

parsing

24h change

market cap

volume

timestamp

provider

Unavailable assets must not break the whole screen.

==================================================
METALS
==================================================

Support:

Gold

Silver

Use reliable free providers.

Cache data.

Never return crypto data for metals.

==================================================
ASSETS
==================================================

Fix completely.

Support:

browse

search

ticker lookup

asset page

price

24h

market cap

volume

watchlist

alerts

live mode

==================================================
WATCHLIST
==================================================

Rename Favorites to:

⭐ Watchlist

Watchlist must immediately display:

price

24h change

trend

provider

last update

Allow:

refresh

sort

search

open asset

live mode

alerts

Sort options:

alphabetical

price

24h gainers

24h losers

==================================================
WALLETS
==================================================

Support:

Bitcoin

Ethereum

BNB

Solana

Tron

Polygon

Arbitrum

Optimism

Base

Support stablecoins:

USDT

USDC

DAI

Support:

ERC20

TRC20

BEP20

Show:

native balance

stablecoin balances

USD value

network

provider

address validation

Do not request seed phrases.

Use free APIs whenever practical.

==================================================
AI CONSULTANT
==================================================

The current implementation is only a Bitcoin template.

Replace it with a real analytical assistant.

First classify:

asset

topic

intent

Supported topics:

crypto

gold

silver

stablecoins

wallets

security

trading

investing

education

networks

portfolio

Examples:

What is TRC20?

Explain TRC20.

Should I buy gold?

Analyze gold.

Should I buy BTC?

Analyze Bitcoin.

How do I buy my first crypto?

Guide beginners.

Never answer gold questions with Bitcoin data.

Never force Bitcoin into unrelated answers.

Ask clarifying questions when necessary.

Current version must remain free.

Prepare clean architecture for future premium AI.

==================================================
PREMIUM
==================================================

Prepare architecture only.

Future premium features:

LLM

portfolio analysis

wallet analysis

risk analysis

AI chat

news explanation

trade assistant

No payment implementation yet.

==================================================
UI
==================================================

Keep Telegram UX clean.

Fast navigation.

Back buttons.

Refresh buttons.

Loading states.

Clear errors.

Consistent formatting.

==================================================
TESTING
==================================================

Run:

git status

compileall

router imports

main.py

focused tests

manual startup

review git diff

update PROJECT_CONTEXT.md

==================================================
FINAL REPORT
==================================================

Always report:

completed work

files changed

validation

remaining issues

recommended next iteration

If the requested scope is too large:

create an implementation plan

finish one safe milestone

stop

wait for the next iteration