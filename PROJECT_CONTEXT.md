# Crypto Hunter - Project Context

## Overview

Crypto Hunter is a Telegram bot built with Python 3.11+ and aiogram 3.x. Windows deployment is verified with Python 3.14.

The goal is to create a production-quality cryptocurrency assistant with a clean architecture.

The project must remain fully asynchronous.

---

## Tech Stack

- Python 3.11+ (Windows deployment verified with Python 3.14)
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

---

## Wallet and Localization Foundation (2026-07-14)

- Added a typed, network-free address detector for EVM and TRON families. EVM
  addresses are compared case-insensitively; TRON uses full Base58Check and the
  `0x41` network prefix rather than a leading-character check.
- Existing Bitcoin, Ethereum, BNB Chain, Solana, and TRON storage and retrieval
  remain intact. Ethereum reads ETH plus allowlisted USDT, USDC, and DAI ERC-20;
  TRON reads TRX and allowlisted USDT TRC-20 through TronGrid.
- TronGrid accepts an optional `TRON_API_KEY`. Native TRX survives malformed
  token data and USDT is labeled explicitly as TRC-20. Ethereum and BSC public
  RPC URLs can be overridden with environment variables.
- Wallet insertion now normalizes EVM casing and checks existing rows with a
  case-insensitive query. No schema was removed or rewritten and no database
  deletion is required.
- Added a centralized English/Ukrainian translation catalog with English
  fallback and missing-key logging. Main-menu Assets, Alerts, Start, Restart,
  Stop, session messages, and News titles/actions now follow stored language.
- The existing conditional `msvcrt`/`fcntl` single-instance implementation was
  preserved. `.crypto-hunter.lock`, `.env`, databases, caches, and virtual
  environments remain ignored.
- Added address and localization tests. No dependencies changed.

## Multi-chain Wallet Discovery (2026-07-14 resumed run)

- EVM and TRON remain the automatically detected address families. EVM syntax
  never claims a particular chain. Ethereum and BNB Smart Chain have public RPC
  defaults; Polygon, Arbitrum One, Base, Optimism, and Avalanche C-Chain are
  enabled only by their configured RPC URLs.
- A central registry owns chain IDs, native symbols, explorers, RPC environment
  variables, and Ethereum's USDT/USDC/DAI ERC-20 allowlist. A generic async
  JSON-RPC client reads native and allowlisted token balances.
- Discovery uses bounded concurrency, individual timeouts, exception isolation,
  a per-address lock, and a short cooldown. Active means a supported non-zero
  balance; zero-balance scans are valid and provider failures are partial.
- The Wallets add flow is now address-first: warning, paste, detection, scan,
  result, then explicit confirmation. TRON uses TronGrid for TRX and USDT
  TRC-20. The bot never accepts private credentials or signs transactions.
- Additive `wallet_profiles` and `wallet_networks` tables store an address once
  and merge networks. Startup idempotently copies legacy rows without deleting
  them, preserving labels/legacy behavior and the existing `wallets` table.
- Wallet flow strings use the central English/Ukrainian catalog. Stable inline
  callback data remains language-independent.
- Files added: `network_registry.py`, `evm_rpc.py`, `wallet_discovery.py`,
  `wallet_discovery_service.py`, discovery and RPC tests. No dependencies were
  changed or files deleted. The machine-specific untracked `run_bot.ps1` was
  preserved and excluded from source control.

Known limitations: full wallet detail/rename/delete/rescan screens and complete
nested-screen localization are not yet implemented. Balance-based discovery can
miss historical activity with zero current balance. Public RPC rate limits can
produce partial results. Next: deep end-to-end Telegram QA, then the AI assistant.

Next recommended work: complete multi-chain wallet discovery and deep
end-to-end Telegram QA, then implement the AI assistant.

## Product-quality UX milestone (2026-07-14)

- Live charts use real cached CoinGecko history and Pillow PNG rendering for
  BTC/ETH/SOL/BNB over 15m, 1h, 4h, 24h, and 7d. `LiveChartManager` owns one
  replaceable task per chat, refreshes at `LIVE_CHART_REFRESH_SECONDS`, and is
  cancelled on navigation, Stop, Restart, shutdown, or session replacement.
- Watchlist Add now presents popular full-name choices and still accepts full,
  partial, case-insensitive name/ticker searches through `asset_service`.
  Stable CoinGecko provider IDs remain in callback data; legacy symbols remain
  the persistence format for compatibility.
- Alert deletion uses `alert:delete:select:<id>` and
  `alert:delete:confirm:<id>`, descriptive localized labels, confirmation, and
  idempotent owner-scoped deletion. Formatting is centralized.
- Consultant questions are classified into concept, asset, comparison,
  stablecoin, DeFi, trading-decision, and market-overview intents. Unrelated
  questions no longer default to BTC. The free fallback is topic-aware; signals
  are scenario-based and appear only for trading questions. Repetitive full
  disclaimers were replaced by a concise notice persisted once per user through
  the existing settings table. Source-language headlines are retained when no
  translation provider is configured, under localized section labels.
- Wallet profiles now have stable-ID list/detail, rename, refresh/rescan, and
  confirmation deletion operations. Profile/network migrations stay additive;
  deletion is owner-scoped and repeated confirmation is harmless.
- Main-menu return paths in Rates, News, Portfolio, Settings, Alerts, and the
  consultant now rebuild from persisted language, addressing the observed
  language reset caused by default-English keyboard construction.
- Added models/services/tests for consultant intent, live charts, alert
  formatting/deletion, and wallet profile operations. No dependency was added.

Known limitations: CoinGecko may provide sparse intraday points; source news
headlines are not translated without an optional provider; deep manual Telegram
QA remains required. Next recommended task: manual end-to-end QA and targeted
polish from real-device results.

## Administrator QA subsystem (2026-07-14)

- Added an independent `python -m qa_bot` entry point that reads only
  `QA_BOT_TOKEN` and `QA_ADMIN_TELEGRAM_ID`, uses
  `.crypto-hunter-qa.lock`, and can coexist with the production polling process.
  Missing/invalid QA configuration fails closed. Unauthorized users receive only
  `Access denied`; identifiers and tokens are never reported or logged.
- `qa_bot.models` defines typed scenario, result, severity, status, and run
  report models. `ScenarioRunner` provides deterministic discovery, suite
  filtering, per-scenario timeouts, bounded concurrency, cancellation,
  failure isolation, progress callbacks, and one-active-run protection.
- Registered smoke, localization, Live, Favorites, Alerts, AI, and Wallet suites
  in `qa/scenarios`. Standard checks reuse application services and mocks, make
  no provider requests, never poll Telegram, and initialize schema only in a
  temporary SQLite path. Real-provider checks remain disabled by default.
- The administrator controller supports Start/Help, suite commands, status,
  scenario listing, cancellation, latest report delivery, confirmed report
  cleanup, and Codex-prompt generation. It has no arbitrary command execution,
  source-editing, commit, push, deployment, or Codex invocation capability.
- `reporting.py` produces redacted Telegram summaries, Markdown, JSON, bug
  sections, and consolidated failed-scenario prompts. `storage.py` accepts only
  generated filename patterns, prevents traversal, lists newest first, and
  scopes deletion to the configured report directory.
- `.env.example` documents QA configuration without values. `.gitignore`
  excludes generated reports, QA databases/logs, and the QA lock. GitHub issue
  variables define a disabled future boundary; publishing is not implemented.
- No new dependency was required. Next milestone: real Telegram E2E using a
  dedicated user account through Telethon or Pyrogram, then optional explicit
  GitHub Issue → Codex PR automation.

## Real Telegram E2E client (2026-07-14)

- Added `qa_e2e`, a separate Telethon user-client CLI. It never starts the main
  bot or administrator QA bot and never reads their tokens. Configuration is
  environment-only and E2E refuses to run unless `E2E_ENABLED=true`.
- `python -m qa_e2e auth` performs first-time authorization only through the
  local console. Login codes use local `input`; Telegram 2FA uses `getpass` and
  is never stored, logged, reported, accepted via Telegram, or passed as a CLI
  argument. Session paths are restricted to `qa/e2e_sessions`.
- `TelegramE2EClient` resolves exactly the configured username, verifies it is a
  bot, records a message baseline, reads a bounded set of new target-chat
  messages/edits, waits for a stable response, and captures sanitized text,
  keyboard labels, media type, limited message IDs, and response timing.
- Central selectors normalize English/Ukrainian labels and reject payments,
  URLs, login buttons, and Web Apps. No external links are followed and no
  arbitrary target, path, or shell command can be supplied.
- E2E scenarios reuse `qa_bot` Scenario/Result/RunReport and cover real Smoke,
  Localization, Live, Favorites, Alerts safety, AI relevance, and public-wallet
  flows. The default non-destructive mode skips persistent deletion/cleanup.
- E2E Markdown/JSON reports and failure-only Codex prompts use the existing
  redaction/reporting pipeline. Storage is constrained to allowlisted E2E report
  and artifact filenames. Admin QA integration is read-only: status, scenario
  listing, latest report, and latest failure prompt. Remote login and execution
  are deliberately unavailable.
- Added Telethon as the only user-client dependency. Sessions, journals,
  reports, evidence, media, and E2E logs are ignored. Next milestone: optional
  GitHub Issue creation and Codex PR automation, then controlled human-approved
  deployment.

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
## Production Telegram route isolation (July 2026)

## Ethereum/Tron wallet hardening (2026-07-15)

- The address-first wallet flow now limits EVM discovery to Ethereum for this
  sprint while preserving older chain integrations for compatibility. Tron
  continues to require a valid mainnet Base58Check payload.
- Provider amounts use `Decimal`; ETH/TRX and USDT zero balances are retained
  explicitly. SQLite persists balances as text along with native symbol,
  last-success timestamp, refresh status, and a safe error code.
- Additive, idempotent `wallet_profiles` migrations preserve existing rows.
  A failed refresh marks prior values stale without erasing them. Per-address
  locks coalesce concurrent scans and a configurable TTL avoids repeat calls.
- `TRON_API_URL` and `TRONGRID_API_KEY` are supported, with the legacy
  `TRON_API_KEY` retained as a compatibility fallback. The default wallet cap
  is 10 and remains enforced in the service as well as unique-address storage.
- Automated validation: compileall passed; pytest reported 149 passed and 6
  subtests passed. Real Telegram polling and production E2E were not run.

At that checkpoint, EIP-55, complete provider error typing, and expanded wallet
E2E coverage remained for the follow-up completion commit below.

## Ethereum/Tron wallet completion (2026-07-15)

- Mixed-case Ethereum addresses now require EIP-55. A small dependency-free
  legacy Keccak-256 implementation is verified against canonical digest vectors;
  standardized SHA3-256 is not used. Lowercase/uppercase addresses remain valid.
- Wallet providers classify failures with stable safe codes for configuration,
  validation, timeout, rate limit, availability, response, network, contract,
  and unknown errors. Telegram renders localized explanations rather than raw
  exception strings, and stale refreshes preserve prior Decimal-string balances.
- Persistence tests cover duplicates, wallet limits, ownership isolation, and
  stale-value retention. UI tests audit Decimal formatting and Telegram's
  callback limit. The non-destructive E2E wallet scenario now exercises invalid,
  Ethereum, Tron, cancellation, and public-address-only warnings without saving.

## Telegram E2E Live/localization reliability (2026-07-15)

- Real Telegram evidence showed that selecting only the last collected raw
  message was unsafe when fresh responses and edited media messages coexist.
  E2E actions now search newest-to-oldest within the current action result for
  the message that actually owns the stable callback or reply-keyboard action.
- The Live product keyboard was already correct: BTC chart media retains asset,
  15m/1h/4h/24h/7d, refresh, stop, and back callbacks. Regression tests keep
  callback payloads within Telegram's limit and verify production ownership.
- Settings and language keyboards now follow persisted English/Ukrainian state.
  Ukrainian selection stores the canonical value, immediately rebuilds the
  Ukrainian main keyboard, works idempotently for already-Ukrainian users, and
  `/start` verifies persistence in the E2E scenario.

Real Telegram E2E runs showed that direct handler/service tests were not sufficient to prove which aiogram route owned AI questions, Watchlist Add, and Live callbacks. Production dispatcher construction now lives in `app/dispatcher.py`, and the verified routes are registered before their broader feature routers.

- Consultant questions in `ConsultantStates.entering_question` are owned by the dedicated `consultant_question` router and call `answer_consultant_question`. Market Analysis remains a separate explicit button and no longer shares ownership of question messages.
- `watchlist:add` is owned by the exact `favorites_add` callback router. It activates typed-search state and sends a fresh English/Ukrainian response with popular full-name buttons and provider-ID callback data. The broader `watchlist:` router explicitly excludes this action.
- `rates:live:*` is owned by the exact `rates_live` router. The default start action renders BTC/1h PNG media with asset/timeframe/refresh/stop/back controls. The broader `rates:` router explicitly excludes Live callbacks.
- The obsolete Binance text-only `LiveTaskManager` was removed from active services, startup cleanup, middleware, and session handlers. `LiveChartManager` is now the only production Live session owner and replaces an existing task per chat.

Regression coverage now includes service responses, actual handler calls, production-router ownership/order, duplicate-owner checks, PNG/media creation, timeframe controls, replacement/cancellation, popular callback IDs, localization, callback-data length, and obsolete-import/source audits. The router audit is `tests/test_production_routing.py`.

Known limitation: mocked dispatcher/handler tests cannot prove Telegram delivery or the deployed process environment. Rerun these manually after deployment; Codex verification must not start polling or run real Telegram E2E automatically:

```powershell
python -m qa_e2e run ai
python -m qa_e2e run favorites
python -m qa_e2e run live
python -m qa_e2e run all
```

## Safe Windows deployment and post-deploy QA (July 2026)

- `deployment/` provides typed deployment/state/health/reporting/notification primitives. State writes use a same-directory temporary file plus atomic replacement, malformed state falls back safely, and the deployment advisory lock is separate from bot, QA-bot, and E2E locks.
- `DeploymentOrchestrator` is operation-injected for deterministic tests. It enforces candidate verification before production stop/update, smoke-first E2E, configurable rollback, full-E2E degraded success by default, rollback health reporting, and suppression of a previously blocked commit.
- Sanitized templates in `scripts/windows` cover the restart-safe bot launcher, candidate-worktree auto deploy, Task Scheduler XML install/removal, safe status inspection, failed-commit clearing, and backup-before-copy local setup. Templates contain no private paths or credentials and are never executed automatically by Codex.
- Candidate verification uses a detached Git worktree and per-commit virtual environment. It installs explicit production and test requirements, then runs compileall and the complete pytest suite before production is stopped. The production branch updates only through validated fast-forward ancestry.
- `Live` production health checks are process/path/tree scoped: exactly one logical production `main.py` tree, stable health window, startup/polling log marker, no immediate traceback, and crash-loop protection. `ParentProcessId` folds a Windows Python 3.14 venv launcher and its underlying interpreter descendants into one instance, while the root executable must equal the active configured Python and independent roots remain duplicates. Rollback restores the validated old commit and previous Python pointer, restarts once, and verifies health.
- Real E2E runs smoke first and full second using the existing local authorized session. Missing authorization is a configuration failure; unattended scripts never request login codes. Smoke failure rolls back by default; full-suite failure keeps the healthy deployment running but marks it `deployed_with_e2e_failures` by default.
- One-shot QA notifications use only the existing admin token/ID environment configuration and bounded retries. Notification failure is non-fatal and no second QA polling process starts. Read-only commands are `/deploy_status`, `/deploy_last`, `/deploy_reports`, and `/deploy_failed_commit`; no deploy/shell/rollback Telegram command exists.
- Runtime state, reports, logs, candidate data, virtual environments, and locks are ignored. `requirements-dev.txt` explicitly provides pytest for unattended candidate verification.

Remaining limitation: the scripts and process/log checks are extensively mocked/audited but have not been executed against the production clone or Task Scheduler during Codex implementation. The first local installation and deployment must be supervised using the README checklist.

## Windows PowerShell 5.1 deployment compatibility fixes (July 2026)

- Removed the fixed Python minor-version selector. Bootstrap Python is a configurable full path, preferring the valid production venv and otherwise resolving `py` without a minor selector. Candidate creation always uses `python -m venv`; Windows is verified with Python 3.14.5.
- Replaced direct native stderr redirection in the launcher with `Start-Process`, separate stdout/stderr files, `-Wait -PassThru`, and the native process `ExitCode`. Normal application logging on stderr no longer terminates Windows PowerShell 5.1.
- Removed `ConvertFrom-Json -AsHashtable`. Deployment and clear-state scripts use `PSCustomObject`, safely add missing properties, and write UTF-8 without BOM. Their shared PowerShell 5.1 atomic-file helper uses a deterministic same-directory `.atomic-backup` with `File.Replace` for existing destinations and same-volume `File.Move` for missing destinations. It verifies the destination, deletes the backup only after success, and restores the original when replacement fails; no template passes a null or empty backup path. Clear-state emits success only after replacement succeeds.
- Active-Python changes are atomic and validated. Rollback selects a valid previous pointer or explicit default production venv before mutation, restores source and pointer before start, reconciles exact path-scoped process trees to zero child-first, then requires exactly one healthy logical tree. Rollback reports source, pointer, process, and health outcomes independently.
- Task installation/removal checks native `schtasks.exe` exit codes. Local setup lists replacements, warns about local edits, backs up every existing generated script, and requires explicit confirmation.

The auto-deploy scheduled task must remain disabled until these updated templates are installed locally and a supervised deployment succeeds.
