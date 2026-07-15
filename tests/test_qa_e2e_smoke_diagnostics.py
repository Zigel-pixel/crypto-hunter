from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, Mock

from qa_bot.models import FailureCategory
from qa_e2e.config import E2EConfig
from qa_e2e.models import (
    ActionResult,
    ActionTiming,
    CollectionPoll,
    MessageEvidence,
    MessageObservation,
)
from qa_e2e.scenarios.flows import (
    _smoke_diagnostic_details,
    _telegram_timing_diagnostics,
    build_scenarios,
)


ACTION_SERVER_DATE = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)


def _config() -> E2EConfig:
    return E2EConfig(
        True,
        1,
        "test-hash",
        "+10000000000",
        "CryptoHunterTestBot",
        Path("qa/e2e_sessions/test"),
        Path("qa/e2e_reports"),
        Path("qa/e2e_artifacts"),
        settle_seconds=2,
        product_response_sla=20,
    )


def _keyboard_message(
    message_id: int,
    *,
    local_latency: float,
    server_delay: float,
    first_observed_at: float | None = None,
) -> MessageEvidence:
    return MessageEvidence(
        message_id,
        ACTION_SERVER_DATE + timedelta(seconds=server_delay),
        "Ваш сеанс активний.",
        None,
        (),
        ("📈 Курси", "⚙ Налаштування"),
        local_latency,
        first_observed_at=110.0 + local_latency if first_observed_at is None else first_observed_at,
        poll_iteration=2,
        observation_source="history",
        markup_kind="reply_keyboard",
    )


def _result(
    messages: tuple[MessageEvidence, ...],
    *,
    polls: tuple[CollectionPoll, ...] = (),
    observations: tuple[MessageObservation, ...] = (),
    reason: str = "qualifying_response_settled",
) -> ActionResult:
    first_observed = min(
        (message.first_observed_at for message in messages if message.first_observed_at is not None),
        default=None,
    )
    earliest_server = min(
        (message.timestamp for message in messages if message.timestamp is not None),
        default=None,
    )
    timing = ActionTiming(
        100.0,
        100.0,
        100.1,
        100.2,
        110.0,
        first_observed,
        133.0,
        collection_deadline_at=133.0,
        product_action_server_date=ACTION_SERVER_DATE,
    )
    return ActionResult(
        "/start",
        10,
        messages,
        min((message.response_seconds for message in messages), default=None),
        33.0,
        timing,
        polls=polls,
        observations=observations,
        collection_reason=reason,
        collection_poll_count=len(polls),
        earliest_server_date=earliest_server,
        earliest_observation_at=first_observed,
    )


async def _smoke_outcome(result: ActionResult):
    client = Mock()
    client.send = AsyncMock(return_value=result)
    scenario = next(
        item for item in build_scenarios(client, _config())
        if item.id == "e2e.smoke.start"
    )
    return await scenario.check()


class SmokeTimingDiagnosticTests(unittest.IsolatedAsyncioTestCase):
    async def test_server_and_local_timelines_are_separate_and_server_delta_is_diagnostic_only(self) -> None:
        message = _keyboard_message(12, local_latency=0.4, server_delay=30.0)
        result = _result((message,))

        outcome = await _smoke_outcome(result)

        self.assertTrue(outcome.passed)
        self.assertIn("product_action_server_timestamp=2026-07-15T12:00:00.000Z", outcome.actual)
        self.assertIn("qualifying_response_server_timestamp=2026-07-15T12:00:30.000Z", outcome.actual)
        self.assertIn("telegram_server_delta_diagnostic=+30.000s_diagnostic_only", outcome.actual)
        self.assertIn("qualifying_first_local_observation=+10.400s", outcome.actual)
        self.assertIn("product_latency=+0.400s", outcome.actual)
        sla = next(item for item in outcome.assertions if item.name == "response_within_product_sla")
        self.assertTrue(sla.passed)

    async def test_local_qualifying_observation_still_enforces_twenty_second_sla(self) -> None:
        message = _keyboard_message(12, local_latency=20.1, server_delay=0.1)
        outcome = await _smoke_outcome(_result((message,)))

        self.assertFalse(outcome.passed)
        self.assertEqual(outcome.failure_category, FailureCategory.PRODUCT_RESPONSE_TIMEOUT)
        self.assertEqual(outcome.failed_predicate, "response_within_product_sla")
        self.assertIn("telegram_server_delta_diagnostic=+0.100s_diagnostic_only", outcome.actual)
        self.assertIn("product_latency=+20.100s", outcome.actual)

    async def test_plain_response_does_not_replace_first_qualifying_keyboard(self) -> None:
        plain = MessageEvidence(
            11,
            ACTION_SERVER_DATE + timedelta(milliseconds=100),
            "Завантаження",
            None,
            (),
            (),
            0.1,
            first_observed_at=110.1,
            poll_iteration=1,
            observation_source="history",
            markup_kind="none",
        )
        first_keyboard = _keyboard_message(12, local_latency=0.5, server_delay=0.4)
        latest_keyboard = _keyboard_message(13, local_latency=0.8, server_delay=0.7)

        outcome = await _smoke_outcome(_result((plain, first_keyboard, latest_keyboard)))

        self.assertTrue(outcome.passed)
        self.assertIn("first_qualifying_id=12", outcome.actual)
        self.assertIn("qualifying_latency=0.5", outcome.actual)
        self.assertIn("qualifying_response_server_timestamp=2026-07-15T12:00:00.400Z", outcome.actual)

    async def test_recovery_collection_settles_on_response_but_start_waits_for_keyboard(self) -> None:
        plain = MessageEvidence(11, ACTION_SERVER_DATE, "ok", None, (), (), 0.1)
        keyboard = _keyboard_message(12, local_latency=0.2, server_delay=0.2)
        client = Mock()
        client.send = AsyncMock(side_effect=(
            ActionResult("/restart", 10, (plain,), 0.1, 0.1),
            ActionResult("/stop", 10, (plain,), 0.1, 0.1),
            ActionResult("/start", 10, (keyboard,), 0.2, 0.2),
        ))
        scenario = next(
            item for item in build_scenarios(client, _config())
            if item.id == "e2e.smoke.sessions"
        )

        outcome = await scenario.check()

        self.assertTrue(outcome[0])
        calls = client.send.await_args_list
        self.assertEqual([call.args[0] for call in calls], ["/restart", "/stop", "/start"])
        self.assertTrue(calls[0].kwargs["settle_when"]((plain,)))
        self.assertTrue(calls[1].kwargs["settle_when"]((plain,)))
        self.assertFalse(calls[2].kwargs["settle_when"]((plain,)))
        self.assertTrue(calls[2].kwargs["settle_when"]((plain, keyboard)))

    async def test_poll_and_message_observations_are_compact_and_safe(self) -> None:
        message = _keyboard_message(12, local_latency=0.4, server_delay=0.2)
        polls = (
            CollectionPoll(1, 110.0, 112.0, 2.0, "timeout", (),
                           exception_type="TimeoutError"),
            CollectionPoll(2, 113.0, 113.05, 0.05, "ok", (11, 12, 13),
                           batch_observation_limited=True),
        )
        observations = (
            MessageObservation(11, False, False, ACTION_SERVER_DATE, 113.05, 3.05, 2,
                               "history", "none", False, "wrong_sender"),
            MessageObservation(12, True, False, message.timestamp, 110.4, 0.4, 2,
                               "history", "reply_keyboard", True),
            MessageObservation(13, False, True, ACTION_SERVER_DATE, 113.05, 3.05, 2,
                               "history", "none", False,
                               "phone +380 50 123 45 67 api_key=do-not-report"),
        )

        result = _result((message,), polls=polls, observations=observations)
        diagnostics = _telegram_timing_diagnostics(result, message)
        details = _smoke_diagnostic_details(result)

        self.assertIn("collection_poll_count=2", diagnostics)
        self.assertIn("history_rpc_timeout_count=1", diagnostics)
        self.assertIn("batch_observation_precision_limited=1", diagnostics)
        self.assertIn("final_collection_reason=qualifying_response_settled", diagnostics)
        self.assertIn("p1(start=+10.000s,end=+12.000s,duration=2.000s,outcome=timeout,ids=none,source=history_batch,batch_limited=0,exception=TimeoutError)", details)
        self.assertIn("p2(start=+13.000s,end=+13.050s,duration=0.050s,outcome=ok,ids=11,12,13,source=history_batch,batch_limited=1,exception=none)", details)
        self.assertIn("m11(sender_match=0,outgoing=0", details)
        self.assertIn("m12(sender_match=1,outgoing=0", details)
        self.assertIn("markup=reply_keyboard,accepted=1", details)
        self.assertNotIn("380", details)
        self.assertNotIn("do-not-report", details)
        self.assertLess(len(details), 2000)

    async def test_long_poll_trace_has_explicit_deterministic_omission_marker(self) -> None:
        message = _keyboard_message(12, local_latency=0.4, server_delay=0.2)
        polls = tuple(
            CollectionPoll(index, 110.0 + index, 110.01 + index, 0.01, "ok", ())
            for index in range(1, 31)
        )

        details = _smoke_diagnostic_details(_result((message,), polls=polls, reason="deadline"))

        self.assertLess(len(details), 2000)
        self.assertIn("final_collection_reason=deadline", details)
        self.assertIn("collection_poll_count=30", details)
        self.assertIn("p1(", details)
        self.assertIn("p30(", details)
        self.assertIn("entries_omitted", details)


if __name__ == "__main__":
    unittest.main()
