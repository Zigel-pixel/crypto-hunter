from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, Mock, patch

from telethon.tl import types as tl_types

from qa_e2e.client import (
    E2EClientError,
    TelegramE2EClient,
    create_telethon_client,
)
from qa_e2e.config import E2EConfig


TARGET_ID = 99


def _config(
    *,
    session_path: Path = Path("qa/e2e_sessions/test"),
    history_rpc_timeout_seconds: float = 0.05,
    history_poll_interval_seconds: float = 0.01,
) -> E2EConfig:
    return E2EConfig(
        True,
        1,
        "test-hash",
        "+10000000000",
        "CryptoHunterTestBot",
        session_path,
        Path("qa/e2e_reports"),
        Path("qa/e2e_artifacts"),
        settle_seconds=0.02,
        history_rpc_timeout_seconds=history_rpc_timeout_seconds,
        history_poll_interval_seconds=history_poll_interval_seconds,
    )


def _message(
    message_id: int,
    *,
    sender_id: int = TARGET_ID,
    outgoing: bool = False,
    server_date: datetime | None = None,
    markup: object | None = None,
    text: str = "response",
) -> Mock:
    buttons = None
    if isinstance(markup, (tl_types.ReplyKeyboardMarkup, tl_types.ReplyInlineMarkup)):
        buttons = [list(row.buttons) for row in markup.rows]
    return Mock(
        id=message_id,
        sender_id=sender_id,
        out=outgoing,
        date=server_date,
        edit_date=None,
        message=text,
        media=None,
        buttons=buttons,
        reply_markup=markup,
    )


def _reply_keyboard() -> tl_types.ReplyKeyboardMarkup:
    button = tl_types.KeyboardButton("📈 Курси")
    return tl_types.ReplyKeyboardMarkup([
        tl_types.KeyboardButtonRow([button]),
    ])


def _has_main_keyboard(messages) -> bool:
    return any("📈 Курси" in message.reply_buttons for message in messages)


class IncrementalCollectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_slow_first_history_rpc_is_bounded_then_second_poll_finds_reply(self) -> None:
        raw = AsyncMock()
        wrapper = TelegramE2EClient(_config(), raw)
        wrapper.target = Mock(id=TARGET_ID)
        action_server_date = datetime.now(timezone.utc)
        response_server_date = action_server_date + timedelta(milliseconds=10)
        response = _message(
            12,
            server_date=response_server_date,
            markup=_reply_keyboard(),
        )
        calls = 0

        async def history(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                await asyncio.Event().wait()
            return [response]

        raw.get_messages.side_effect = history
        product_action_sent_at = time.monotonic()
        result = await wrapper.collect(
            10,
            "/start",
            product_action_sent_at,
            timeout=0.5,
            settle_when=_has_main_keyboard,
            product_action_server_date=action_server_date,
        )

        self.assertEqual(calls, 2)
        self.assertEqual([poll.outcome for poll in result.polls], ["timeout", "success"])
        self.assertEqual(result.polls[0].exception_type, "TimeoutError")
        self.assertLess(result.polls[0].rpc_duration_seconds, 0.25)
        self.assertEqual(result.polls[1].discovered_message_ids, (12,))
        self.assertTrue(result.polls[1].batch_observation_limited)
        self.assertEqual(result.collection_reason, "predicate_satisfied")
        self.assertEqual(result.collection_poll_count, 2)
        self.assertEqual(result.earliest_server_date, response_server_date)
        self.assertEqual(result.messages[0].timestamp, response_server_date)
        self.assertEqual(result.messages[0].poll_iteration, 2)
        self.assertEqual(result.messages[0].markup_kind, "ReplyKeyboardMarkup")
        self.assertGreater(result.messages[0].first_observed_at, product_action_sent_at)
        self.assertLess(result.messages[0].response_seconds, 0.5)
        self.assertEqual(result.earliest_observation_at, result.messages[0].first_observed_at)

    async def test_incremental_empty_poll_then_message_poll(self) -> None:
        raw = AsyncMock()
        wrapper = TelegramE2EClient(_config(), raw)
        wrapper.target = Mock(id=TARGET_ID)
        response = _message(
            12,
            server_date=datetime.now(timezone.utc),
            markup=_reply_keyboard(),
        )
        raw.get_messages.side_effect = ([], [response])

        result = await wrapper.collect(
            10,
            "/start",
            time.monotonic(),
            timeout=0.5,
            settle_when=_has_main_keyboard,
        )

        self.assertEqual(raw.get_messages.await_count, 2)
        self.assertEqual(result.polls[0].discovered_message_ids, ())
        self.assertEqual(result.polls[1].discovered_message_ids, (12,))
        self.assertEqual(result.messages[0].poll_iteration, 2)
        self.assertEqual(result.collection_reason, "predicate_satisfied")

    async def test_server_date_and_local_observation_remain_separate(self) -> None:
        raw = AsyncMock()
        wrapper = TelegramE2EClient(_config(), raw)
        wrapper.target = Mock(id=TARGET_ID)
        server_date = datetime.now(timezone.utc) - timedelta(seconds=5)
        response = _message(12, server_date=server_date, markup=_reply_keyboard())
        raw.get_messages.return_value = [response]
        product_action_sent_at = time.monotonic()

        result = await wrapper.collect(
            10,
            "/start",
            product_action_sent_at,
            timeout=0.5,
            settle_when=_has_main_keyboard,
        )

        evidence = result.messages[0]
        self.assertEqual(evidence.timestamp, server_date)
        self.assertIsInstance(evidence.first_observed_at, float)
        self.assertGreaterEqual(evidence.first_observed_at, product_action_sent_at)
        self.assertAlmostEqual(
            evidence.response_seconds,
            evidence.first_observed_at - product_action_sent_at,
            places=6,
        )

    async def test_rejected_messages_are_diagnostic_only(self) -> None:
        raw = AsyncMock()
        wrapper = TelegramE2EClient(_config(), raw)
        wrapper.target = Mock(id=TARGET_ID)
        base_date = datetime.now(timezone.utc)
        stale = _message(9, server_date=base_date)
        outgoing = _message(11, sender_id=1, outgoing=True, server_date=base_date)
        wrong_sender = _message(12, sender_id=77, server_date=base_date)
        accepted = _message(
            13,
            server_date=base_date + timedelta(seconds=1),
            markup=_reply_keyboard(),
        )
        raw.get_messages.return_value = [accepted, wrong_sender, outgoing, stale]

        result = await wrapper.collect(
            10,
            "/start",
            time.monotonic(),
            timeout=0.5,
            settle_when=_has_main_keyboard,
        )

        self.assertEqual([message.message_id for message in result.messages], [13])
        self.assertEqual(result.outgoing_message_ids, (11,))
        observations = {item.message_id: item for item in result.observations}
        self.assertEqual(observations[9].exclusion_reason, "stale_or_boundary")
        self.assertFalse(observations[9].accepted)
        self.assertTrue(observations[11].outgoing)
        self.assertEqual(observations[11].exclusion_reason, "outgoing")
        self.assertFalse(observations[12].expected_sender_match)
        self.assertEqual(observations[12].exclusion_reason, "unexpected_sender")
        self.assertTrue(observations[13].expected_sender_match)
        self.assertTrue(observations[13].accepted)
        self.assertIsNone(observations[13].exclusion_reason)

    def test_markup_kinds_are_explicit(self) -> None:
        wrapper = TelegramE2EClient(_config(), AsyncMock())
        inline_button = tl_types.KeyboardButtonCallback("Open", b"safe:open")
        cases = (
            (
                tl_types.ReplyInlineMarkup([
                    tl_types.KeyboardButtonRow([inline_button]),
                ]),
                "ReplyInlineMarkup",
            ),
            (_reply_keyboard(), "ReplyKeyboardMarkup"),
            (tl_types.ReplyKeyboardHide(), "ReplyKeyboardHide"),
            (tl_types.ReplyKeyboardForceReply(), "ReplyKeyboardForceReply"),
        )

        for markup, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(
                    wrapper._markup_kind(_message(1, markup=markup)),
                    expected,
                )

    def test_telethon_factory_disables_hidden_flood_sleep(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            session_path = Path(temp_dir) / "e2e" / "session"
            config = _config(session_path=session_path)
            created = object()
            with patch("telethon.TelegramClient", return_value=created) as constructor:
                client = create_telethon_client(config)

        self.assertIs(client, created)
        constructor.assert_called_once_with(
            str(session_path),
            config.api_id,
            config.api_hash,
            flood_sleep_threshold=0,
        )

    async def test_baseline_history_request_has_independent_timeout(self) -> None:
        async def never_returns(*args, **kwargs):
            await asyncio.Event().wait()

        raw = AsyncMock()
        raw.get_messages.side_effect = never_returns
        wrapper = TelegramE2EClient(
            _config(history_rpc_timeout_seconds=0.03),
            raw,
        )
        wrapper.target = Mock(id=TARGET_ID)
        started = time.monotonic()

        with self.assertRaisesRegex(E2EClientError, "baseline request timed out"):
            await wrapper.baseline()

        self.assertLess(time.monotonic() - started, 0.3)
        raw.get_messages.assert_awaited_once_with(wrapper.target, limit=1)

    async def test_keyboard_hydration_history_request_has_independent_timeout(self) -> None:
        async def never_returns(*args, **kwargs):
            await asyncio.Event().wait()

        raw = AsyncMock()
        raw.get_messages.side_effect = never_returns
        wrapper = TelegramE2EClient(
            _config(history_rpc_timeout_seconds=0.03),
            raw,
        )
        wrapper.target = Mock(id=TARGET_ID)
        started = time.monotonic()

        with self.assertRaisesRegex(E2EClientError, "keyboard history request timed out"):
            await wrapper._refresh_reply_keyboard_state()

        self.assertLess(time.monotonic() - started, 0.3)
        raw.get_messages.assert_awaited_once_with(wrapper.target, limit=50)

    async def test_send_uses_outgoing_message_as_baseline_without_history_request(self) -> None:
        raw = AsyncMock()
        server_date = datetime.now(timezone.utc)
        outgoing = _message(
            42,
            sender_id=1,
            outgoing=True,
            server_date=server_date,
            text="/start",
        )
        raw.send_message.return_value = outgoing
        wrapper = TelegramE2EClient(_config(), raw)
        wrapper.target = Mock(id=TARGET_ID)
        expected = Mock()
        wrapper.collect = AsyncMock(return_value=expected)

        result = await wrapper.send("/start")

        self.assertIs(result, expected)
        raw.get_messages.assert_not_awaited()
        call = wrapper.collect.await_args
        self.assertEqual(call.args[0], 42)
        self.assertIs(call.kwargs["outgoing_message"], outgoing)
        self.assertEqual(call.kwargs["product_action_server_date"], server_date)


if __name__ == "__main__":
    unittest.main()
