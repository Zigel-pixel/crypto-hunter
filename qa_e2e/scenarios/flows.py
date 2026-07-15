from __future__ import annotations

import asyncio
import re
import time
from collections.abc import Awaitable, Callable

from qa_bot.models import CheckResult, FailureCategory, NamedAssertion, Scenario, Severity
from qa_e2e.client import TelegramE2EClient
from qa_e2e.config import E2EConfig
from qa_e2e.evidence import contains_raw_error

PUBLIC_EVM_TEST_ADDRESS = "0x000000000000000000000000000000000000dEaD"
PUBLIC_TRON_TEST_ADDRESS = "TXLAQ63Xg1NAzckPwKHvzw7CSEmLMEqcdj"
SMOKE_OBSERVATION_POLL_MARGIN_SECONDS = 1


def _latest(result):
    return result.messages[-1] if result.messages else None


def _latest_reply_keyboard(result, expected_actions: tuple[str, ...]):
    expected = {item.casefold() for item in expected_actions}
    for message in reversed(result.messages):
        if message.message_id <= result.baseline_id:
            continue
        labels = {item.casefold() for item in message.reply_buttons}
        if labels & expected:
            return message
    return None


def _first_qualifying_reply_keyboard(result, expected_actions: tuple[str, ...]):
    expected = {item.casefold() for item in expected_actions}
    matches = [message for message in result.messages
               if message.message_id > result.baseline_id
               and {item.casefold() for item in message.reply_buttons} & expected]
    return min(matches, key=lambda item: item.response_seconds, default=None)


def _contains_expected_reply_keyboard(messages, expected_actions: tuple[str, ...]) -> bool:
    expected = {item.casefold() for item in expected_actions}
    return any({item.casefold() for item in message.reply_buttons} & expected
               for message in messages)


async def _start_and_open(client: TelegramE2EClient, candidates: tuple[str, ...]):
    """Make every feature suite independent of smoke and prior keyboard state."""
    started = await client.send("/start")
    if _latest(started) is None:
        raise RuntimeError("No /start response")
    return await client.send_recent_reply_action(candidates)


def _scenario(client: TelegramE2EClient, config: E2EConfig, scenario_id: str, title: str, suite: str, expected: str, action: Callable[[], Awaitable[tuple[bool, str, str]]], *, severity: Severity = Severity.HIGH) -> Scenario:
    return Scenario(scenario_id, title, suite, "Real Telegram interaction with the configured target bot.", expected, action, severity, timeout=config.max_scenario_seconds, tags=("telegram-e2e",), related_modules=("app/handlers", "app/keyboards"), reproduction_steps=(f"Run python -m qa_e2e run {suite}", f"Observe scenario {scenario_id}"))


def build_scenarios(client: TelegramE2EClient, config: E2EConfig) -> tuple[Scenario, ...]:
    async def smoke_start():
        scenario_started_at = time.monotonic()
        expected_actions = ("📈 Rates", "📈 Курси")
        observation_timeout = min(
            config.max_scenario_seconds,
            config.product_response_sla + config.settle_seconds + SMOKE_OBSERVATION_POLL_MARGIN_SECONDS,
        )
        result = await client.send(
            "/start", timeout=observation_timeout,
            scenario_started_at=scenario_started_at,
            readiness_completed_at=scenario_started_at,
            settle_when=lambda messages: _contains_expected_reply_keyboard(messages, expected_actions),
        )
        latest = _latest_reply_keyboard(result, expected_actions)
        first_qualifying = _first_qualifying_reply_keyboard(result, expected_actions)
        qualifying_latency = first_qualifying.response_seconds if first_qualifying is not None else None
        assertions = (
            NamedAssertion("bot_response_received", bool(result.messages), f"messages={len(result.messages)}"),
            NamedAssertion("response_is_fresh", bool(latest and latest.message_id > result.baseline_id), f"baseline={result.baseline_id}"),
            NamedAssertion("response_from_expected_target", first_qualifying is not None, "filtered by target conversation and sender"),
            NamedAssertion("reply_markup_type_is_reply_keyboard", latest is not None),
            NamedAssertion("reply_keyboard_non_empty", bool(latest and latest.reply_buttons)),
            NamedAssertion("known_safe_main_action_present", bool(latest and set(latest.reply_buttons) & {"📈 Rates", "📈 Курси"})),
            NamedAssertion("no_inline_cross_classification", bool(latest is not None and not latest.inline_buttons)),
            NamedAssertion("no_raw_error_leakage", bool(latest is not None and not contains_raw_error(latest.text))),
            NamedAssertion("response_within_product_sla", qualifying_latency is not None and qualifying_latency <= config.product_response_sla,
                           f"qualifying={qualifying_latency}; sla={config.product_response_sla}"),
        )
        failed = next((item.name for item in assertions if not item.passed), None)
        actual = (f"messages={len(result.messages)}, first_qualifying_id="
                  f"{first_qualifying.message_id if first_qualifying else None}, qualifying_latency={qualifying_latency}, "
                  f"reply={latest.reply_buttons if latest else ()}, inline={latest.inline_buttons if latest else ()}; "
                  f"{_timing_evidence(result, qualifying_latency, config.product_response_sla, config.max_scenario_seconds)}")
        category = FailureCategory.PRODUCT_RESPONSE_TIMEOUT if failed == "response_within_product_sla" else FailureCategory.PRODUCT_ASSERTION_FAILED
        return CheckResult(failed is None, actual, _evidence(result), category if failed else None, failed, assertions)

    async def smoke_sessions():
        parts = []
        for command in ("/restart", "/stop", "/start"):
            result = await client.send(command)
            parts.append(f"{command}:{len(result.messages)}")
            if not result.messages or any(contains_raw_error(item.text) for item in result.messages):
                return False, ", ".join(parts), _evidence(result)
            if command == "/start" and _latest_reply_keyboard(result, ("📈 Rates", "📈 Курси")) is None:
                return False, ", ".join(parts), "Recovery readiness probe did not restore the safe main keyboard"
        return True, ", ".join(parts), "Session commands responded without technical errors"

    async def localization():
        start = await client.send("/start")
        if _latest(start) is None: return False, "No /start response", _evidence(start)
        settings = await client.send_recent_reply_action(("⚙ Налаштування", "⚙ Settings"))
        language = await client.send_recent_reply_action(("🌐 Мова", "🌐 Language"))
        selected = await client.send_recent_reply_action(("Українська", "Ukrainian"))
        latest = _latest(selected)
        labels = latest.reply_buttons if latest else ()
        persisted = await client.send("/start")
        persisted_latest = _latest(persisted)
        labels = persisted_latest.reply_buttons if persisted_latest else labels
        ok = any("Активи" in label for label in labels) and any("Сповіщення" in label for label in labels) and not any("Settings" in label for label in labels)
        return ok, f"Ukrainian main labels: {labels}", _evidence(selected)

    async def live():
        rates = await _start_and_open(client, ("📈 Курси", "📈 Rates"))
        chart = await client.click_recent_inline(callback_prefix="rates:live:start", timeout=config.long_timeout)
        media = [item for item in chart.messages if item.media_type]
        labels = tuple(label for item in chart.messages for label in item.inline_buttons)
        expected_timeframes = ("15m", "1h", "4h", "24h", "7d")
        old_mode = any("Live Crypto / USDT" in item.text or "Binance WebSocket" in item.text for item in chart.messages)
        ok = (bool(media) and not old_mode and all(any(tf in label for label in labels) for tf in expected_timeframes)
              and any("BTC" in item.text and any(tf in item.text for tf in expected_timeframes) for item in chart.messages))
        return ok, f"messages={len(chart.messages)}, media={len(media)}, timeframes={labels}, old_mode={old_mode}", _evidence(chart)

    async def favorites():
        opened = await _start_and_open(client, ("⭐ Обране", "⭐ Watchlist", "⭐ Favorites"))
        try:
            chart = await client.click_recent_inline(callback_prefix="watchlist:chart:", timeout=config.long_timeout)
        except LookupError:
            chart = None
        if chart is not None:
            labels = tuple(label for item in chart.messages for label in item.inline_buttons)
            media = any(item.media_type for item in chart.messages)
            ok = media and all(any(value in label for label in labels) for value in ("15m", "1h", "4h", "24h", "7d"))
            return ok, f"chart_media={media}, timeframes={labels}", _evidence(chart)
        raw = client.last_raw_messages[-1] if client.last_raw_messages else None
        if raw is None: return False, "Watchlist message unavailable", _evidence(opened)
        add = await client.click_recent_inline(callback_prefix="watchlist:add")
        labels = tuple(label for item in add.messages for label in item.inline_buttons)
        ok = "Bitcoin (BTC)" in labels and "Ethereum (ETH)" in labels and "Solana (SOL)" in labels
        return ok, f"popular labels={labels}", _evidence(add)

    async def alerts():
        if not config.allow_destructive:
            return True, "Skipped persistent alert creation because destructive scenarios are disabled", "Safety gate active"
        return False, "Alert creation E2E requires a dedicated clean account and remains conservative", "Enable only after reviewing existing account alerts"

    async def ai():
        opened = await _start_and_open(client, ("🤖 AI Консультант", "🤖 AI Consultant"))
        current = _latest(opened)
        if current is None: return False, "AI menu unavailable", _evidence(opened)
        await client.send_recent_reply_action(("💬 Запитати консультанта", "💬 Ask Consultant"))
        response = await client.send("Що ти скажеш про стейблкоїни?", timeout=config.long_timeout)
        text = "\n".join(item.text for item in response.messages)
        topic = all(token in text for token in ("USDT", "USDC", "DAI"))
        risk = any(token in text.casefold() for token in ("емітент", "issuer", "резерв", "reserve", "depeg", "прив’яз"))
        legacy_dump = "Поточна картина ринку" in text or "Current market" in text
        ok = topic and risk and not legacy_dump and not contains_raw_error(text)
        return ok, f"stablecoins={topic}, risk={risk}, legacy_dump={legacy_dump}, messages={len(response.messages)}", _evidence(response)

    async def wallets():
        opened = await _start_and_open(client, ("👛 Гаманці", "👛 Wallets"))
        current = _latest(opened)
        if current is None: return False, "Wallet menu unavailable", _evidence(opened)
        warning = await client.send_recent_reply_action(("➕ Додати гаманець", "➕ Add wallet"))
        warning_text = "\n".join(item.text for item in warning.messages).casefold()
        security_ok = any(term in warning_text for term in ("seed", "приватн", "private key"))
        invalid = await client.send("not-a-wallet")
        invalid_text = "\n".join(item.text for item in invalid.messages).casefold()
        invalid_ok = any(term in invalid_text for term in ("invalid", "некорект"))
        response = await client.send(PUBLIC_EVM_TEST_ADDRESS, timeout=config.long_timeout)
        text = "\n".join(item.text for item in response.messages)
        lowered = text.casefold()
        values = re.findall(r"(?:^|:\s)([0-9][0-9,]*(?:\.[0-9]+)?)", text, re.MULTILINE)
        parseable = all(_parse_balance(value) is not None for value in values)
        standards_ok = not any(symbol in text and "ERC-20" not in text for symbol in ("USDT", "USDC", "DAI"))
        networks_ok = any(name in lowered for name in ("ethereum", "bnb", "polygon", "arbitrum", "base", "optimism", "avalanche", "мереж"))
        provider_error = contains_raw_error(text) or "traceback" in lowered or "json-rpc" in lowered
        outcome = bool(values) or "no supported balances" in lowered or "підтримуваних балансів не знайдено" in lowered
        raw = client.last_raw_messages[-1] if client.last_raw_messages else None
        if raw is None:
            return False, "Ethereum confirmation controls missing", _evidence(response)
        cancelled = await client.click_inline(raw, callback_prefix="wallet:cancel")
        cancel_ok = bool(cancelled.messages)
        wallets_menu = await _start_and_open(client, ("👛 Гаманці", "👛 Wallets"))
        wallet_menu = _latest(wallets_menu) if wallets_menu else None
        add_again = await client.send_recent_reply_action(("➕ Додати гаманець", "➕ Add wallet")) if wallet_menu else None
        tron_ok = False
        if add_again is not None:
            tron = await client.send(PUBLIC_TRON_TEST_ADDRESS, timeout=config.long_timeout)
            tron_text = "\n".join(item.text for item in tron.messages).casefold()
            tron_ok = "tron" in tron_text or "trc-20" in tron_text
            raw = client.last_raw_messages[-1] if client.last_raw_messages else None
            if raw is not None:
                await client.click_inline(raw, callback_prefix="wallet:cancel")
        ok = security_ok and invalid_ok and outcome and parseable and standards_ok and networks_ok and not provider_error and cancel_ok and tron_ok
        return ok, f"security={security_ok}, invalid={invalid_ok}, ethereum={networks_ok}, tron={tron_ok}, cancel={cancel_ok}, provider_error={provider_error}", _evidence(response)

    return (
        _scenario(client, config, "e2e.smoke.start", "Start and main keyboard", "smoke", "Start responds with a safe main reply keyboard", smoke_start, severity=Severity.CRITICAL),
        _scenario(client, config, "e2e.smoke.sessions", "Restart/Stop/Start recovery", "smoke", "Every session command responds without raw errors", smoke_sessions, severity=Severity.CRITICAL),
        _scenario(client, config, "e2e.localization.uk", "Persist Ukrainian language", "localization", "Ukrainian main keyboard is visible after selection", localization),
        _scenario(client, config, "e2e.live.chart", "Real Live chart media", "live", "BTC chart media arrives with timeframe metadata", live),
        _scenario(client, config, "e2e.favorites.popular", "Watchlist chart or popular setup", "favorites", "A saved asset chart renders, or the empty-state add flow offers Bitcoin", favorites),
        _scenario(client, config, "e2e.alerts.safety", "Scoped alert safety", "alerts", "No unrelated alerts are modified", alerts),
        _scenario(client, config, "e2e.ai.stablecoins", "Stablecoin answer relevance", "ai", "Response discusses stablecoins without raw errors", ai),
        _scenario(client, config, "e2e.wallets.public_only", "Public wallet safety", "wallets", "Only a safe public address is used and the bot responds", wallets),
    )


def _evidence(result) -> str:
    return " | ".join(f"id={item.message_id}; media={item.media_type or 'text'}; text={item.text[:200]}; inline={item.inline_buttons}; reply={item.reply_buttons}; t={item.response_seconds:.2f}s" for item in result.messages[:10]) or "No target-bot response"


def _timing_evidence(result, qualifying_latency: float | None = None,
                     product_sla: float | None = None, overall_timeout: float | None = None) -> str:
    timing = result.timing
    if timing is None:
        return "timing=unavailable"
    qualifying_offset = (timing.offset(timing.product_action_sent_at) + qualifying_latency
                         if qualifying_latency is not None else None)
    action_offset = timing.offset(timing.product_action_sent_at)
    product_deadline_offset = (action_offset + product_sla
                               if product_sla is not None else None)
    return "; ".join((
        "scenario_started_at=+0.000s",
        f"readiness_completed_at=+{timing.offset(timing.readiness_completed_at):.3f}s",
        f"boundary_captured_at=+{timing.offset(timing.boundary_captured_at):.3f}s",
        f"send_started_at=+{timing.offset(timing.send_started_at):.3f}s",
        f"product_action_sent_at=+{timing.offset(timing.product_action_sent_at):.3f}s",
        f"first_response_at={_offset(timing.offset(timing.first_response_at))}",
        f"qualifying_response_at={_offset(qualifying_offset)}",
        f"product_latency={_offset(qualifying_latency)}",
        f"product_deadline_at={_offset(product_deadline_offset)}",
        f"collection_deadline_at={_offset(timing.offset(timing.collection_deadline_at))}",
        f"scenario_deadline_at={_offset(overall_timeout)}",
        f"product_sla={product_sla if product_sla is not None else 'unknown'}s",
        f"overall_scenario_timeout={overall_timeout if overall_timeout is not None else 'unknown'}s",
        f"overall_duration={result.total_seconds:.3f}s",
    ))


def _offset(value: float | None) -> str:
    return "none" if value is None else f"+{value:.3f}s"


def _parse_balance(value: str) -> float | None:
    try:
        parsed = float(value.replace(",", ""))
    except ValueError:
        return None
    return parsed if parsed >= 0 and parsed != float("inf") else None


class _raw_message_placeholder:
    """Adapt sanitized evidence for reply-keyboard selection without exposing other chats."""
    def __init__(self, evidence) -> None:
        self.reply_markup = type("Markup", (), {"rows": tuple(type("Row", (), {"buttons": tuple(type("Button", (), {"text": label})() for label in evidence.reply_buttons)})() for _ in (0,))})()
