from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime
import time
from typing import Any

from telethon.errors import RPCError
from telethon.tl import types as tl_types

from qa_e2e.config import E2EConfig
from qa_e2e.evidence import sanitize_text
from qa_e2e.models import (
    ActionResult,
    ActionTiming,
    ActiveReplyKeyboard,
    CollectionPoll,
    MessageEvidence,
    MessageObservation,
)
from qa_e2e.selectors import button_labels, ensure_safe_button, find_inline_button, hides_reply_keyboard, normalize_label, reply_keyboard_labels, reply_keyboard_rows, select_reply_label


class E2EClientError(RuntimeError):
    pass


class TargetNotBot(E2EClientError):
    pass


def create_telethon_client(config: E2EConfig):
    from telethon import TelegramClient
    config.session_path.parent.mkdir(parents=True, exist_ok=True)
    return TelegramClient(
        str(config.session_path), config.api_id, config.api_hash,
        flood_sleep_threshold=0,
    )


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
        try:
            messages = await self._bounded_history(limit=1)
        except asyncio.TimeoutError as exc:
            raise E2EClientError("Telegram history baseline request timed out") from exc
        if not messages:
            return 0
        first = messages[0] if isinstance(messages, (list, tuple)) else messages
        return int(getattr(first, "id", 0))

    async def send(self, text: str, *, timeout: int | None = None,
                   scenario_started_at: float | None = None,
                   readiness_completed_at: float | None = None,
                   settle_when: Callable[[tuple[MessageEvidence, ...]], bool] | None = None) -> ActionResult:
        self._require_target()
        boundary_captured_at = time.monotonic()
        scenario_started_at = boundary_captured_at if scenario_started_at is None else scenario_started_at
        readiness_completed_at = scenario_started_at if readiness_completed_at is None else readiness_completed_at
        send_started_at = time.monotonic()
        outgoing_message = await self.client.send_message(self.target, text)
        product_action_sent_at = time.monotonic()
        baseline = getattr(outgoing_message, "id", None)
        if not isinstance(baseline, int) or baseline <= 0:
            raise E2EClientError("Telegram send result did not include a valid message ID")
        product_action_server_date = self._server_date(outgoing_message)
        return await self.collect(
            baseline, text, product_action_sent_at, timeout=timeout,
            scenario_started_at=scenario_started_at,
            readiness_completed_at=readiness_completed_at,
            boundary_captured_at=boundary_captured_at,
            send_started_at=send_started_at,
            settle_when=settle_when,
            outgoing_message=outgoing_message,
            product_action_server_date=product_action_server_date,
        )

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
        boundary_captured_at = time.monotonic()
        send_started_at = time.monotonic()
        await message.click(data=getattr(button, "data", None))
        product_action_sent_at = time.monotonic()
        return await self.collect(baseline, f"click:{getattr(button, 'text', '')}", product_action_sent_at,
                                  timeout=timeout, include_baseline=True,
                                  scenario_started_at=boundary_captured_at,
                                  readiness_completed_at=boundary_captured_at,
                                  boundary_captured_at=boundary_captured_at,
                                  send_started_at=send_started_at)

    async def click_recent_inline(self, *, callback_prefix: str, timeout: int | None = None) -> ActionResult:
        """Click by stable callback data on the newest fresh owning message."""
        for message in reversed(self.last_raw_messages):
            try:
                find_inline_button(message, callback_prefix=callback_prefix)
            except LookupError:
                continue
            return await self.click_inline(message, callback_prefix=callback_prefix, timeout=timeout)
        raise LookupError("Requested safe inline button was not found in fresh messages")

    async def collect(self, baseline: int, action: str, product_action_sent_at: float, *, timeout: int | None = None,
                      include_baseline: bool = False, scenario_started_at: float | None = None,
                      readiness_completed_at: float | None = None, boundary_captured_at: float | None = None,
                      send_started_at: float | None = None,
                      settle_when: Callable[[tuple[MessageEvidence, ...]], bool] | None = None,
                      outgoing_message: Any | None = None,
                      product_action_server_date: datetime | None = None) -> ActionResult:
        self._require_target()
        scenario_started_at = product_action_sent_at if scenario_started_at is None else scenario_started_at
        readiness_completed_at = product_action_sent_at if readiness_completed_at is None else readiness_completed_at
        boundary_captured_at = product_action_sent_at if boundary_captured_at is None else boundary_captured_at
        send_started_at = product_action_sent_at if send_started_at is None else send_started_at
        deadline = product_action_sent_at + (timeout or self.config.default_timeout)
        seen: dict[tuple[int, str, str | None, tuple[str, ...], tuple[str, ...]], MessageEvidence] = {}
        raw_seen: dict[int, Any] = {}
        observation_seen: set[tuple[int, object, str, bool, bool]] = set()
        observations: list[MessageObservation] = []
        polls: list[CollectionPoll] = []
        outgoing_ids: set[int] = set()
        first_response_at: float | None = None
        last_change = product_action_sent_at
        collection_reason = "deadline"
        had_history_timeout = False
        had_history_error = False
        if outgoing_message is not None:
            outgoing_id = int(getattr(outgoing_message, "id", 0))
            outgoing_ids.add(outgoing_id)
            observations.append(MessageObservation(
                outgoing_id, False, True, self._server_date(outgoing_message),
                product_action_sent_at, 0.0, 0, "send_result",
                self._markup_kind(outgoing_message), False, "outgoing",
            ))
        poll_iteration = 0
        while time.monotonic() < deadline:
            poll_iteration += 1
            minimum = max(0, baseline - 1) if include_baseline else baseline
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            rpc_started_at = time.monotonic()
            messages: Any = ()
            outcome = "success"
            exception_type: str | None = None
            try:
                messages = await asyncio.wait_for(
                    self.client.get_messages(self.target, min_id=minimum, limit=50),
                    timeout=min(self.config.history_rpc_timeout_seconds, remaining),
                )
            except asyncio.TimeoutError:
                outcome = "timeout"
                exception_type = "TimeoutError"
                had_history_timeout = True
            except (RPCError, OSError) as exc:
                outcome = "error"
                exception_type = type(exc).__name__
                had_history_error = True
            rpc_finished_at = time.monotonic()
            raw_messages = tuple(messages or ())
            discovered_ids = tuple(sorted({
                int(getattr(message, "id", 0)) for message in raw_messages
                if int(getattr(message, "id", 0)) > 0
            }))
            polls.append(CollectionPoll(
                poll_iteration, rpc_started_at, rpc_finished_at,
                max(0.0, rpc_finished_at - rpc_started_at), outcome,
                discovered_ids, "history_batch", bool(discovered_ids), exception_type,
            ))
            now = rpc_finished_at
            for message in reversed(raw_messages):
                message_id = int(getattr(message, "id", 0))
                outgoing = getattr(message, "out", False) is True
                sender_id = getattr(message, "sender_id", None)
                target_id = getattr(self.target, "id", None)
                expected_sender_match = not (
                    isinstance(sender_id, int) and isinstance(target_id, int)
                    and sender_id != target_id
                )
                fresh = message_id > baseline or (include_baseline and message_id == baseline)
                accepted = fresh and not outgoing and expected_sender_match
                exclusion_reason = None
                if not fresh:
                    exclusion_reason = "stale_or_boundary"
                elif outgoing:
                    exclusion_reason = "outgoing"
                    outgoing_ids.add(message_id)
                elif not expected_sender_match:
                    exclusion_reason = "unexpected_sender"
                markup_kind = self._markup_kind(message)
                observation_key = (
                    message_id, getattr(message, "edit_date", None), markup_kind,
                    outgoing, expected_sender_match,
                )
                if observation_key not in observation_seen:
                    observation_seen.add(observation_key)
                    observations.append(MessageObservation(
                        message_id, expected_sender_match, outgoing,
                        self._server_date(message), now,
                        max(0.0, now - product_action_sent_at), poll_iteration,
                        "history_batch", markup_kind, accepted, exclusion_reason,
                    ))
                if not accepted:
                    continue
                evidence = self._evidence(
                    message, max(0.0, now - product_action_sent_at),
                    edited=bool(getattr(message, "edit_date", None)),
                    first_observed_at=now, poll_iteration=poll_iteration,
                    markup_kind=markup_kind,
                )
                self._process_reply_keyboard(message)
                raw_seen[message_id] = message
                key = (message_id, evidence.text, evidence.media_type,
                       evidence.inline_buttons, evidence.reply_buttons)
                if key not in seen:
                    seen[key] = evidence
                    if first_response_at is None:
                        first_response_at = now
                    last_change = now
            collected = tuple(seen.values())
            if collected and settle_when is not None and settle_when(collected):
                collection_reason = "predicate_satisfied"
                break
            if (outcome == "success" and collected and settle_when is None
                    and now - last_change >= self.config.settle_seconds):
                collection_reason = "settled"
                break
            sleep_seconds = min(
                self.config.history_poll_interval_seconds,
                max(0.0, deadline - time.monotonic()),
            )
            if sleep_seconds > 0:
                await asyncio.sleep(sleep_seconds)
        if collection_reason == "deadline":
            if had_history_timeout:
                collection_reason = "deadline_after_history_timeout"
            elif had_history_error:
                collection_reason = "deadline_after_history_error"
        ordered = tuple(sorted(seen.values(), key=lambda item: (item.message_id, item.edited)))
        self.last_raw_messages = tuple(raw_seen[key] for key in sorted(raw_seen))
        finished_at = time.monotonic()
        first = min((item.response_seconds for item in ordered), default=None)
        server_dates = tuple(item.timestamp for item in ordered if isinstance(item.timestamp, datetime))
        observation_times = tuple(
            item.first_observed_at for item in ordered if item.first_observed_at is not None
        )
        timing = ActionTiming(scenario_started_at, readiness_completed_at, boundary_captured_at,
                              send_started_at, product_action_sent_at, first_response_at, finished_at,
                              collection_deadline_at=deadline,
                              product_action_server_date=product_action_server_date)
        return ActionResult(
            action, baseline, ordered, first, finished_at - scenario_started_at,
            timing, tuple(sorted(outgoing_ids)), tuple(polls), tuple(observations),
            collection_reason, len(polls), min(server_dates, default=None),
            min(observation_times, default=None),
        )

    def _evidence(self, message: Any, elapsed: float, *, edited: bool,
                  first_observed_at: float, poll_iteration: int,
                  markup_kind: str) -> MessageEvidence:
        media = getattr(message, "media", None)
        media_type = type(media).__name__ if media is not None else None
        return MessageEvidence(
            int(getattr(message, "id", 0)), self._server_date(message),
            sanitize_text(getattr(message, "message", "") or ""), media_type,
            button_labels(message), reply_keyboard_labels(message), elapsed, edited,
            first_observed_at, poll_iteration, "history_batch", markup_kind,
        )

    def _require_target(self) -> None:
        if self.target is None:
            raise E2EClientError("Target bot has not been resolved")

    async def _bounded_history(self, **kwargs: Any) -> Any:
        return await asyncio.wait_for(
            self.client.get_messages(self.target, **kwargs),
            timeout=self.config.history_rpc_timeout_seconds,
        )

    @staticmethod
    def _markup_kind(message: Any) -> str:
        markup = getattr(message, "reply_markup", None)
        if isinstance(markup, tl_types.ReplyInlineMarkup):
            return "ReplyInlineMarkup"
        if isinstance(markup, tl_types.ReplyKeyboardMarkup):
            return "ReplyKeyboardMarkup"
        if isinstance(markup, tl_types.ReplyKeyboardHide):
            return "ReplyKeyboardHide"
        if isinstance(markup, tl_types.ReplyKeyboardForceReply):
            return "ReplyKeyboardForceReply"
        return "none" if markup is None else type(markup).__name__

    @staticmethod
    def _server_date(message: Any) -> datetime | None:
        value = getattr(message, "date", None)
        return value if isinstance(value, datetime) else None

    @property
    def active_reply_keyboard(self) -> ActiveReplyKeyboard | None:
        return self._reply_keyboards.get(self._target_key()) if self.target is not None else None

    def _target_key(self) -> str:
        value = getattr(self.target, "id", None) or getattr(self.target, "username", None)
        return str(value)

    def _process_reply_keyboard(self, message: Any) -> None:
        if getattr(message, "out", False) is True:
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
        try:
            messages = await self._bounded_history(limit=50)
        except asyncio.TimeoutError as exc:
            raise E2EClientError("Telegram keyboard history request timed out") from exc
        self._reply_keyboards.pop(self._target_key(), None)
        for message in reversed(tuple(messages or ())):
            self._process_reply_keyboard(message)
