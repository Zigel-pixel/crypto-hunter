from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable

from qa_bot.models import Scenario, Severity
from qa_e2e.client import TelegramE2EClient
from qa_e2e.config import E2EConfig
from qa_e2e.evidence import contains_raw_error

PUBLIC_EVM_TEST_ADDRESS = "0x000000000000000000000000000000000000dEaD"
PUBLIC_TRON_TEST_ADDRESS = "TXLAQ63Xg1NAzckPwKHvzw7CSEmLMEqcdj"


def _latest(result):
    return result.messages[-1] if result.messages else None


def _scenario(client: TelegramE2EClient, config: E2EConfig, scenario_id: str, title: str, suite: str, expected: str, action: Callable[[], Awaitable[tuple[bool, str, str]]], *, severity: Severity = Severity.HIGH) -> Scenario:
    return Scenario(scenario_id, title, suite, "Real Telegram interaction with the configured target bot.", expected, action, severity, timeout=config.max_scenario_seconds, tags=("telegram-e2e",), related_modules=("app/handlers", "app/keyboards"), reproduction_steps=(f"Run python -m qa_e2e run {suite}", f"Observe scenario {scenario_id}"))


def build_scenarios(client: TelegramE2EClient, config: E2EConfig) -> tuple[Scenario, ...]:
    async def smoke_start():
        result = await client.send("/start")
        latest = _latest(result)
        ok = latest is not None and bool(latest.reply_buttons) and not contains_raw_error(latest.text) and (result.first_response_seconds or 999) <= config.default_timeout
        return ok, f"messages={len(result.messages)}, first={result.first_response_seconds}, keyboard={latest.reply_buttons if latest else ()}", _evidence(result)

    async def smoke_sessions():
        parts = []
        for command in ("/restart", "/stop", "/start"):
            result = await client.send(command)
            parts.append(f"{command}:{len(result.messages)}")
            if not result.messages or any(contains_raw_error(item.text) for item in result.messages):
                return False, ", ".join(parts), _evidence(result)
        return True, ", ".join(parts), "Session commands responded without technical errors"

    async def localization():
        start = await client.send("/start")
        message = _latest(start)
        if message is None: return False, "No /start response", _evidence(start)
        settings = await client.send_reply_button(_raw_message_placeholder(message), ("⚙ Налаштування", "⚙ Settings"))
        current = _latest(settings)
        if current is None: return False, "Settings did not respond", _evidence(settings)
        language = await client.send_reply_button(_raw_message_placeholder(current), ("🌐 Language", "🌐 Мова"))
        current = _latest(language)
        if current is None: return False, "Language screen missing", _evidence(language)
        selected = await client.send_reply_button(_raw_message_placeholder(current), ("Ukrainian", "Українська"))
        latest = _latest(selected)
        labels = latest.reply_buttons if latest else ()
        ok = any("Активи" in label for label in labels) and any("Сповіщення" in label for label in labels)
        return ok, f"Ukrainian main labels: {labels}", _evidence(selected)

    async def live():
        start = await client.send("/start")
        message = _latest(start)
        if message is None: return False, "No main menu", _evidence(start)
        rates = await client.send_reply_button(_raw_message_placeholder(message), ("📈 Курси", "📈 Rates"))
        raw = client.last_raw_messages[-1] if client.last_raw_messages else None
        if raw is None: return False, "Rates response lacks inspectable message", _evidence(rates)
        chart = await client.click_inline(raw, callback_prefix="rates:live:start", timeout=config.long_timeout)
        media = [item for item in chart.messages if item.media_type]
        labels = tuple(label for item in chart.messages for label in item.inline_buttons)
        expected_timeframes = ("15m", "1h", "4h", "24h", "7d")
        old_mode = any("Live Crypto / USDT" in item.text or "Binance WebSocket" in item.text for item in chart.messages)
        ok = (bool(media) and not old_mode and all(any(tf in label for label in labels) for tf in expected_timeframes)
              and any("BTC" in item.text and any(tf in item.text for tf in expected_timeframes) for item in chart.messages))
        return ok, f"messages={len(chart.messages)}, media={len(media)}, timeframes={labels}, old_mode={old_mode}", _evidence(chart)

    async def favorites():
        start = await client.send("/start"); message = _latest(start)
        if message is None: return False, "No main menu", _evidence(start)
        opened = await client.send_reply_button(_raw_message_placeholder(message), ("⭐ Обране", "⭐ Watchlist"))
        raw = client.last_raw_messages[-1] if client.last_raw_messages else None
        if raw is None: return False, "Watchlist message unavailable", _evidence(opened)
        add = await client.click_inline(raw, callback_prefix="watchlist:add")
        labels = tuple(label for item in add.messages for label in item.inline_buttons)
        ok = "Bitcoin (BTC)" in labels and "Ethereum (ETH)" in labels and "Solana (SOL)" in labels
        return ok, f"popular labels={labels}", _evidence(add)

    async def alerts():
        if not config.allow_destructive:
            return True, "Skipped persistent alert creation because destructive scenarios are disabled", "Safety gate active"
        return False, "Alert creation E2E requires a dedicated clean account and remains conservative", "Enable only after reviewing existing account alerts"

    async def ai():
        start = await client.send("/start"); message = _latest(start)
        if message is None: return False, "No main menu", _evidence(start)
        opened = await client.send_reply_button(_raw_message_placeholder(message), ("🤖 AI Консультант", "🤖 AI Consultant"))
        current = _latest(opened)
        if current is None: return False, "AI menu unavailable", _evidence(opened)
        await client.send_reply_button(_raw_message_placeholder(current), ("💬 Запитати консультанта", "💬 Ask Consultant"))
        response = await client.send("Що ти скажеш про стейблкоїни?", timeout=config.long_timeout)
        text = "\n".join(item.text for item in response.messages)
        topic = all(token in text for token in ("USDT", "USDC", "DAI"))
        risk = any(token in text.casefold() for token in ("емітент", "issuer", "резерв", "reserve", "depeg", "прив’яз"))
        legacy_dump = "Поточна картина ринку" in text or "Current market" in text
        ok = topic and risk and not legacy_dump and not contains_raw_error(text)
        return ok, f"stablecoins={topic}, risk={risk}, legacy_dump={legacy_dump}, messages={len(response.messages)}", _evidence(response)

    async def wallets():
        start = await client.send("/start"); message = _latest(start)
        if message is None: return False, "No main menu", _evidence(start)
        opened = await client.send_reply_button(_raw_message_placeholder(message), ("👛 Гаманці", "👛 Wallets"))
        current = _latest(opened)
        if current is None: return False, "Wallet menu unavailable", _evidence(opened)
        warning = await client.send_reply_button(_raw_message_placeholder(current), ("➕ Додати гаманець", "➕ Add wallet"))
        response = await client.send(PUBLIC_EVM_TEST_ADDRESS, timeout=config.long_timeout)
        text = "\n".join(item.text for item in response.messages)
        lowered = text.casefold()
        values = re.findall(r"(?:^|:\s)([0-9][0-9,]*(?:\.[0-9]+)?)", text, re.MULTILINE)
        parseable = all(_parse_balance(value) is not None for value in values)
        standards_ok = not any(symbol in text and "ERC-20" not in text for symbol in ("USDT", "USDC", "DAI"))
        networks_ok = any(name in lowered for name in ("ethereum", "bnb", "polygon", "arbitrum", "base", "optimism", "avalanche", "мереж"))
        provider_error = contains_raw_error(text) or "traceback" in lowered or "json-rpc" in lowered
        outcome = bool(values) or "no supported balances" in lowered or "підтримуваних балансів не знайдено" in lowered
        ok = outcome and parseable and standards_ok and networks_ok and not provider_error
        return ok, f"messages={len(response.messages)}, values={len(values)}, parseable={parseable}, standards={standards_ok}, networks={networks_ok}, provider_error={provider_error}", _evidence(response)

    return (
        _scenario(client, config, "e2e.smoke.start", "Start and main keyboard", "smoke", "Start responds with a safe main reply keyboard", smoke_start, severity=Severity.CRITICAL),
        _scenario(client, config, "e2e.smoke.sessions", "Restart/Stop/Start recovery", "smoke", "Every session command responds without raw errors", smoke_sessions, severity=Severity.CRITICAL),
        _scenario(client, config, "e2e.localization.uk", "Persist Ukrainian language", "localization", "Ukrainian main keyboard is visible after selection", localization),
        _scenario(client, config, "e2e.live.chart", "Real Live chart media", "live", "BTC chart media arrives with timeframe metadata", live),
        _scenario(client, config, "e2e.favorites.popular", "Popular favorite buttons", "favorites", "Bitcoin (BTC) appears as an exact choice", favorites),
        _scenario(client, config, "e2e.alerts.safety", "Scoped alert safety", "alerts", "No unrelated alerts are modified", alerts),
        _scenario(client, config, "e2e.ai.stablecoins", "Stablecoin answer relevance", "ai", "Response discusses stablecoins without raw errors", ai),
        _scenario(client, config, "e2e.wallets.public_only", "Public wallet safety", "wallets", "Only a safe public address is used and the bot responds", wallets),
    )


def _evidence(result) -> str:
    return " | ".join(f"id={item.message_id}; media={item.media_type or 'text'}; text={item.text[:200]}; inline={item.inline_buttons}; reply={item.reply_buttons}; t={item.response_seconds:.2f}s" for item in result.messages[:10]) or "No target-bot response"


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
