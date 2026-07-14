# Crypto Hunter

Crypto Hunter is an MVP Telegram bot for cryptocurrency market tracking, portfolio utilities, alerts, news, and read-only public-wallet monitoring. Wallet features accept public addresses only. Never send a seed phrase, private key, password, or recovery phrase.

## Features

- Cached market rates, Binance WebSocket quotes, and managed live price charts
- Watchlist search by common name/ticker, assets, portfolio, descriptive alerts, and crypto news
- Read-only Bitcoin, Solana, TRON, and configured EVM wallet balances
- Ethereum allowlisted ERC-20 balances: USDT, USDC, and DAI
- TRON native TRX and allowlisted USDT TRC-20 balances
- English and Ukrainian main menus, session controls, and news UI
- Per-user `/start`, `/restart`, and `/stop` session controls
- Topic-aware consultant for assets, comparisons, stablecoins, DeFi, and scenario-based market questions
- A concise AI uncertainty notice is shown once per user instead of repeating on every response
- SQLite persistence and cross-platform single-instance protection

The address-first wallet flow recognizes EVM and TRON addresses, scans compatible enabled networks concurrently, and asks before saving. EVM syntax cannot identify a chain. Existing manually saved Bitcoin and Solana wallets remain supported.

Live charts support BTC, ETH, SOL, and BNB across 15m, 1h, 4h, 24h, and 7d. They use cached real CoinGecko history and update one managed Telegram media message. Each chat owns at most one live-chart task.

## Supported Networks

| Network | Native balance | Token balances | Notes |
| --- | --- | --- | --- |
| Bitcoin | BTC | None | Existing address validation and public provider |
| Ethereum | ETH | USDT, USDC, DAI (ERC-20) | Enabled by a public default RPC; balance-based discovery |
| BNB Smart Chain | BNB | None | Enabled by a public default RPC; balance-based discovery |
| Polygon | POL | None | Enabled only when `POLYGON_RPC_URL` is configured |
| Arbitrum One | ETH | None | Enabled only when `ARBITRUM_RPC_URL` is configured |
| Base | ETH | None | Enabled only when `BASE_RPC_URL` is configured |
| Optimism | ETH | None | Enabled only when `OPTIMISM_RPC_URL` is configured |
| Avalanche C-Chain | AVAX | None | Enabled only when `AVALANCHE_RPC_URL` is configured |
| Solana | SOL | None | Public JSON-RPC |
| TRON | TRX | USDT (TRC-20) | TronGrid public endpoint; optional API key |

Public endpoints are rate limited and may return partial or temporarily unavailable data. Current EVM support is balance based and does not infer historical activity.

## Architecture

- `app/handlers`: Telegram event coordination and FSM flows
- `app/services`: business logic, persistence orchestration, localization consumers
- `app/integrations`: CoinGecko, WebSocket, blockchain, and provider clients
- `app/database`: additive SQLite initialization and migrations
- `app/models`: typed application and provider results
- `app/keyboards`: reply and inline keyboard builders
- `app/middlewares`: user-session and live-task lifecycle enforcement
- `tests`: isolated unit tests with provider calls mocked where applicable

## Requirements

- Python 3.13
- Telegram bot token
- SQLite and an internet connection
- Optional provider API keys for higher limits or richer Ethereum data

## Installation

```powershell
git clone https://github.com/Zigel-pixel/crypto-hunter.git
cd crypto-hunter
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python main.py
```

```bash
git clone https://github.com/Zigel-pixel/crypto-hunter.git
cd crypto-hunter
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python main.py
```

## Configuration

`BOT_TOKEN` is required. `ALCHEMY_API_KEY`, `ETHERSCAN_API_KEY`, and `TRON_API_KEY` are optional; blank values use limited public fallback behavior. `ETHEREUM_RPC_URL` and `BSC_RPC_URL` override their public defaults. `POLYGON_RPC_URL`, `ARBITRUM_RPC_URL`, `BASE_RPC_URL`, `OPTIMISM_RPC_URL`, and `AVALANCHE_RPC_URL` enable those networks. `WALLET_SCAN_TIMEOUT_SECONDS` is the per-network timeout and `WALLET_MAX_CONCURRENT_SCANS` bounds concurrency. `ALERT_CHECK_INTERVAL_SECONDS` controls alert checks. `LIVE_CHART_REFRESH_SECONDS` controls periodic chart replacement and defaults to 45 seconds.

The bot prevents a second local polling process with `.crypto-hunter.lock`; the operating system releases the advisory lock after shutdown or a crash. For the current optional Windows 24/7 setup, Task Scheduler starts a local `run_bot.ps1`. That file is machine-specific and intentionally untracked. Stop the scheduled task before production updates, pull and test, then restart it; never launch a second manual polling process.

## Testing

```bash
python -m compileall -q app tests main.py
python -m pytest
```

No lint or static-type command is currently configured.

## Administrator QA Bot

Crypto Hunter includes a separate internal QA controller. It runs reusable
service-level and mocked-handler scenarios and reports results through a second
Telegram bot. It does not use `BOT_TOKEN`, start the production bot, access the
production database, act as a Telegram user, or click the main bot through the
Bot API.

Configure `QA_BOT_TOKEN` with a token belonging to a separate Telegram bot and
set `QA_ADMIN_TELEGRAM_ID` to the only authorized administrator. Never reuse the
production bot token. Launch the controller independently:

```powershell
python -m qa_bot
```

```bash
python -m qa_bot
```

The QA process uses `.crypto-hunter-qa.lock`, so it can run alongside the main
bot's separate lock. It refuses to start when its required QA configuration is
missing or invalid.

Commands include `/run_all`, `/run_smoke`, `/run_localization`, `/run_live`,
`/run_favorites`, `/run_alerts`, `/run_ai`, `/run_wallets`, `/status`,
`/list_scenarios`, `/cancel`, `/last_report`, `/clear_reports`, and
`/codex_prompt`. Only the configured administrator is accepted.

Suites reuse application validators, formatters, registries, chart rendering,
and consultant routing. Standard scenarios mock or avoid all external providers
and initialize SQLite only inside temporary directories. Real provider checks
are opt-in with `QA_REAL_PROVIDER_CHECKS=true` and are not required for a
successful standard run.

Each run generates Markdown and JSON under `QA_REPORTS_DIR` (default
`qa/reports`). Failures include expected/actual behavior, sanitized evidence,
reproduction steps, suspected modules, and recommended investigation. Generated
reports, Codex prompts, QA databases, logs, and the QA lock are ignored by Git.
`/codex_prompt` produces a file containing verified failures; it never invokes
Codex or modifies the repository. `/clear_reports` requires confirmation and
deletes only matching generated report files inside the configured directory.

GitHub issue publishing is disabled and not implemented in this milestone.
`QA_GITHUB_ISSUES_ENABLED`, repository, and token variables reserve a safe
future integration boundary; no token is required and no issue is created.

This is internal automated QA, not true Telegram end-to-end testing. A future
milestone can use a dedicated Telegram user account with Telethon or Pyrogram,
followed later by explicit GitHub Issue → Codex PR automation.

## Real Telegram E2E QA

`qa_e2e` is a separate Telethon user client for controlled interaction with the
actual configured Crypto Hunter bot. Unlike the internal QA bot, it sends real
messages as a dedicated Telegram test user, reads only the configured target-bot
chat, inspects reply/inline keyboards, performs safe callback clicks, records
timings and media metadata, and produces reports compatible with the existing QA
report model.

Install dependencies, create a dedicated Telegram test account, and obtain an
API ID/API hash from Telegram's official application management page. Put the
E2E settings in the local `.env`; never commit or share them. Keep
`E2E_ENABLED=false` until the account and target are intentionally ready.

First-time authorization is local and interactive:

```powershell
python -m qa_e2e auth
```

```bash
python -m qa_e2e auth
```

The Telegram login code is requested only in that local console. If Telegram
requires 2FA, the password is read with a non-echoing secure prompt. Codes and
passwords are never accepted by the administrator QA bot, environment variables,
command-line arguments, logs, reports, or source files. The generated Telethon
session is equivalent to a sensitive account credential: never upload, send, or
copy it to another person.

Commands:

```text
python -m qa_e2e status
python -m qa_e2e list
python -m qa_e2e run smoke
python -m qa_e2e run localization
python -m qa_e2e run live
python -m qa_e2e run favorites
python -m qa_e2e run alerts
python -m qa_e2e run ai
python -m qa_e2e run wallets
python -m qa_e2e run all
python -m qa_e2e reports
python -m qa_e2e clear-reports
python -m qa_e2e clear-artifacts
```

The target username comes only from configuration and must resolve to a Telegram
bot. Inline selectors reject payment, URL, login, and Web App buttons. The client
does not inspect unrelated chats, contacts, or account-wide history. Evidence is
bounded to new messages/edits in the target chat and sanitizes text, phone-like
values, credentials, button labels, media types, limited IDs, and timings.

`E2E_ALLOW_DESTRUCTIVE_SCENARIOS=false` is the default. In this mode alert,
favorite, and wallet deletion/cleanup is skipped. When explicitly enabled, a
scenario may modify only records it created for the dedicated E2E account.

Reports are stored under `qa/e2e_reports`; optional bounded media metadata or
downloads belong under `qa/e2e_artifacts`. Reports, artifacts, sessions, journals,
and logs are ignored by Git. The administrator QA bot exposes read-only
`/e2e_status`, `/e2e_list`, `/e2e_last_report`, and `/e2e_codex_prompt` commands.
It cannot authorize Telethon or request login codes/2FA, and remote E2E execution
is intentionally not enabled.

Real Telegram tests depend on Telegram availability, public providers, the
dedicated account's existing state, and current production deployment. The next
milestone is optional GitHub Issue creation and Codex PR automation, followed by
controlled deployment only after explicit human approval.

## Wallet Security

Crypto Hunter is read-only. It stores public wallet addresses, never requests private credentials, cannot sign transactions, and cannot transfer or withdraw funds.

## Localization

English is the fallback language. Ukrainian is supported for the main menu, session controls, news, consultant controls, alert management, and wallet profile flows. Back navigation resolves the persisted language instead of rebuilding an English-default main keyboard.

## Known Limitations

- Public RPC and TronGrid rate limits and partial provider outages
- EVM discovery is balance-based and can miss historical activity with zero current balance
- Token reading uses a selected allowlist rather than unbounded discovery
- Some nested screens still contain English-only text
- SQLite is appropriate for the MVP but not large horizontal deployments
- The AI consultant is not a complete analytical assistant
- News headlines inside analysis remain in their source language when no optional translation provider exists; section labels follow the interface language

## Roadmap

- Deep end-to-end Telegram QA
- Complete nested-screen localization
- Implement the planned AI assistant
- Broaden safe token discovery, deployment, and monitoring
- Consider PostgreSQL when scaling requires it

## License

No license has been selected yet.
