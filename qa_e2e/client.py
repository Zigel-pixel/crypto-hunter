from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import time
from typing import Any

from qa_e2e.config import E2EConfig
from qa_e2e.evidence import sanitize_text
from qa_e2e.models import ActionResult, MessageEvidence
from qa_e2e.selectors import button_labels, ensure_safe_button, find_inline_button, reply_keyboard_labels, select_reply_label


class E2EClientError(RuntimeError):
    pass


class TargetNotBot(E2EClientError):
    pass


def create_telethon_client(config: E2EConfig):
    from telethon import TelegramClient
    config.session_path.parent.mkdir(parents=True, exist_ok=True)
    return TelegramClient(str(config.session_path), config.api_id, config.api_hash)


class TelegramE2EClient:
    def __init__(self, config: E2EConfig, client: Any | None = None) -> None:
        self.config = config
        self.client = client or create_telethon_client(config)
        self.target: Any | None = None
        self.last_raw_messages: tuple[Any, ...] = ()

    async def connect(self) -> None:
        await self.client.connect()
        if not await self.client.is_user_authorized():
            raise E2EClientError("Local console authorization is required")
        entity = await self.client.get_entity(self.config.target_username)
        if not getattr(entity, "bot", False):
            raise TargetNotBot("Configured target is not a Telegram bot")
        username = str(getattr(entity, "username", "")).casefold()
        if username != self.config.target_username.casefold():
            raise TargetNotBot("Resolved target does not match configured bot")
        self.target = entity

    async def disconnect(self) -> None:
        await self.client.disconnect()

    async def authorized(self) -> bool:
        await self.client.connect()
        try:
            return bool(await self.client.is_user_authorized())
        finally:
            await self.client.disconnect()

    async def baseline(self) -> int:
        self._require_target()
        messages = await self.client.get_messages(self.target, limit=1)
        if not messages:
            return 0
        first = messages[0] if isinstance(messages, (list, tuple)) else messages
        return int(getattr(first, "id", 0))

    async def send(self, text: str, *, timeout: int | None = None) -> ActionResult:
        self._require_target()
        baseline = await self.baseline()
        started = time.monotonic()
        await self.client.send_message(self.target, text)
        return await self.collect(baseline, text, started, timeout=timeout)

    async def send_reply_button(self, message: Any, candidates: tuple[str, ...], *, timeout: int | None = None) -> ActionResult:
        return await self.send(select_reply_label(message, candidates), timeout=timeout)

    async def click_inline(self, message: Any, *, text: str | None = None, callback_prefix: str | None = None, timeout: int | None = None) -> ActionResult:
        self._require_target()
        button = find_inline_button(message, text=text, callback_prefix=callback_prefix)
        ensure_safe_button(button)
        baseline = await self.baseline()
        started = time.monotonic()
        await message.click(data=getattr(button, "data", None))
        return await self.collect(baseline, f"click:{getattr(button, 'text', '')}", started, timeout=timeout, include_baseline=True)

    async def collect(self, baseline: int, action: str, started: float, *, timeout: int | None = None, include_baseline: bool = False) -> ActionResult:
        self._require_target()
        deadline = started + (timeout or self.config.default_timeout)
        seen: dict[tuple[int, str, str | None, tuple[str, ...]], MessageEvidence] = {}
        raw_seen: dict[int, Any] = {}
        last_change = time.monotonic()
        while time.monotonic() < deadline:
            minimum = max(0, baseline - 1) if include_baseline else baseline
            messages = await self.client.get_messages(self.target, min_id=minimum, limit=50)
            now = time.monotonic()
            for message in reversed(tuple(messages or ())):
                message_id = int(getattr(message, "id", 0))
                if message_id < baseline or (message_id == baseline and not include_baseline):
                    continue
                evidence = self._evidence(message, now - started, edited=bool(getattr(message, "edit_date", None)))
                raw_seen[message_id] = message
                key = (message_id, evidence.text, evidence.media_type, evidence.inline_buttons)
                if key not in seen:
                    seen[key] = evidence
                    last_change = now
            if seen and now - last_change >= self.config.settle_seconds:
                break
            await asyncio.sleep(0.25)
        ordered = tuple(sorted(seen.values(), key=lambda item: (item.message_id, item.edited)))
        self.last_raw_messages = tuple(raw_seen[key] for key in sorted(raw_seen))
        first = min((item.response_seconds for item in ordered), default=None)
        return ActionResult(action, baseline, ordered, first, time.monotonic() - started)

    def _evidence(self, message: Any, elapsed: float, *, edited: bool) -> MessageEvidence:
        media = getattr(message, "media", None)
        media_type = type(media).__name__ if media is not None else None
        return MessageEvidence(int(getattr(message, "id", 0)), getattr(message, "date", None), sanitize_text(getattr(message, "message", "") or ""), media_type, button_labels(message), reply_keyboard_labels(message), elapsed, edited)

    def _require_target(self) -> None:
        if self.target is None:
            raise E2EClientError("Target bot has not been resolved")
