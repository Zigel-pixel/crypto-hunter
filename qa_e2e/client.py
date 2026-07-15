from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import time
from typing import Any

from qa_e2e.config import E2EConfig
from qa_e2e.evidence import sanitize_text
from qa_e2e.models import ActionResult, ActiveReplyKeyboard, MessageEvidence
from qa_e2e.selectors import button_labels, ensure_safe_button, find_inline_button, hides_reply_keyboard, normalize_label, reply_keyboard_labels, reply_keyboard_rows, select_reply_label


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
        self._reply_keyboards: dict[str, ActiveReplyKeyboard] = {}

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
        await self._refresh_reply_keyboard_state()

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

    async def send_recent_reply_action(self, candidates: tuple[str, ...], *, timeout: int | None = None) -> ActionResult:
        """Send a safe action from Telegram's target-scoped persistent keyboard."""
        state = self.active_reply_keyboard
        available = {normalize_label(label): label for label in state.labels} if state else {}
        for candidate in candidates:
            if normalize_label(candidate) in available:
                return await self.send(available[normalize_label(candidate)], timeout=timeout)
        safe_labels = tuple(sanitize_text(label) for label in state.labels) if state else ()
        detail = "none" if state is None else f"source_message={state.source_message_id}, labels={safe_labels}"
        raise LookupError(f"Requested reply-keyboard action is unavailable; active_keyboard={detail}")

    async def click_inline(self, message: Any, *, text: str | None = None, callback_prefix: str | None = None, timeout: int | None = None) -> ActionResult:
        self._require_target()
        button = find_inline_button(message, text=text, callback_prefix=callback_prefix)
        ensure_safe_button(button)
        baseline = await self.baseline()
        started = time.monotonic()
        await message.click(data=getattr(button, "data", None))
        return await self.collect(baseline, f"click:{getattr(button, 'text', '')}", started, timeout=timeout, include_baseline=True)

    async def click_recent_inline(self, *, callback_prefix: str, timeout: int | None = None) -> ActionResult:
        """Click by stable callback data on the newest fresh owning message."""
        for message in reversed(self.last_raw_messages):
            try:
                find_inline_button(message, callback_prefix=callback_prefix)
            except LookupError:
                continue
            return await self.click_inline(message, callback_prefix=callback_prefix, timeout=timeout)
        raise LookupError("Requested safe inline button was not found in fresh messages")

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
                self._process_reply_keyboard(message)
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

    @property
    def active_reply_keyboard(self) -> ActiveReplyKeyboard | None:
        return self._reply_keyboards.get(self._target_key()) if self.target is not None else None

    def _target_key(self) -> str:
        value = getattr(self.target, "id", None) or getattr(self.target, "username", None)
        return str(value)

    def _process_reply_keyboard(self, message: Any) -> None:
        if getattr(message, "out", False):
            return
        key = self._target_key()
        rows = reply_keyboard_rows(message)
        if rows:
            self._reply_keyboards[key] = ActiveReplyKeyboard(
                rows, int(getattr(message, "id", 0)), getattr(message, "date", None)
            )
        elif hides_reply_keyboard(message):
            self._reply_keyboards.pop(key, None)

    async def _refresh_reply_keyboard_state(self) -> None:
        """Rebuild state from bounded recent history for this target only."""
        messages = await self.client.get_messages(self.target, limit=50)
        self._reply_keyboards.pop(self._target_key(), None)
        for message in reversed(tuple(messages or ())):
            self._process_reply_keyboard(message)
