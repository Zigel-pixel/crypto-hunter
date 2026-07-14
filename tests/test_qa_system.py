from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from unittest.mock import AsyncMock, Mock

from qa_bot.config import QAConfigError, load_qa_config
from qa_bot.models import RunReport, Scenario, ScenarioResult, Severity, Status
from qa_bot.reporting import codex_prompt, json_report, markdown_report
from qa_bot.scenario_runner import RunAlreadyActive, ScenarioRunner
from qa_bot.security import is_authorized, redact
from qa_bot.storage import ReportStorage
from qa_bot.handlers import authorize_event


async def passed(): return True, "ok", ""


def sample_report(actual: str = "actual") -> RunReport:
    now = datetime.now(timezone.utc)
    result = ScenarioResult("x", "Failure", "smoke", now, now, 0.1, Status.FAILED, Severity.HIGH, "expected", actual, related_modules=("app/x.py",), reproduction_steps=("Run x",))
    return RunReport("smoke", now, now, "feat/market-core", "abc123", "Windows · Python", (result,))


class QAConfigTests(unittest.TestCase):
    def test_missing_and_invalid_config(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(QAConfigError): load_qa_config(load_env_file=False)
        with patch.dict(os.environ, {"QA_BOT_TOKEN": "qa", "QA_ADMIN_TELEGRAM_ID": "invalid"}, clear=True):
            with self.assertRaises(QAConfigError): load_qa_config(load_env_file=False)

    def test_valid_config_and_safe_defaults(self) -> None:
        with patch.dict(os.environ, {"QA_BOT_TOKEN": "qa-token", "QA_ADMIN_TELEGRAM_ID": "123", "QA_MAX_PARALLEL_SCENARIOS": "bad"}, clear=True):
            config = load_qa_config(load_env_file=False)
        self.assertEqual(config.admin_id, 123)
        self.assertEqual(config.max_parallel, 3)
        self.assertFalse(config.github_issues_enabled)

    def test_authorization(self) -> None:
        self.assertTrue(is_authorized(7, 7))
        self.assertFalse(is_authorized(8, 7))
        self.assertFalse(is_authorized(None, 7))


class QAAuthorizationHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_unauthorized_message_reveals_only_access_denied(self) -> None:
        event = Mock()
        event.from_user = Mock(id=8)
        event.answer = AsyncMock()
        self.assertFalse(await authorize_event(event, 7))
        event.answer.assert_awaited_once_with("Access denied")

    async def test_authorized_user_is_accepted_without_response(self) -> None:
        event = Mock()
        event.from_user = Mock(id=7)
        event.answer = AsyncMock()
        self.assertTrue(await authorize_event(event, 7))
        event.answer.assert_not_awaited()


class ScenarioRunnerTests(unittest.IsolatedAsyncioTestCase):
    async def test_discovery_filter_and_order(self) -> None:
        runner = ScenarioRunner((Scenario("b", "B", "live", "", "", passed), Scenario("a", "A", "smoke", "", "", passed)))
        self.assertEqual([item.id for item in runner.scenarios], ["a", "b"])
        report = await runner.run("smoke")
        self.assertEqual(report.results[0].status, Status.PASSED)

    async def test_timeout_is_isolated(self) -> None:
        async def slow(): await asyncio.sleep(1); return True, "late", ""
        runner = ScenarioRunner((Scenario("a", "slow", "smoke", "", "", slow, timeout=0.01), Scenario("b", "pass", "smoke", "", "", passed)), max_parallel=2)
        report = await runner.run()
        self.assertEqual([item.status for item in report.results], [Status.ERROR, Status.PASSED])

    async def test_cancel_and_one_active_run(self) -> None:
        started = asyncio.Event()
        async def slow(): started.set(); await asyncio.sleep(10); return True, "", ""
        runner = ScenarioRunner((Scenario("a", "slow", "smoke", "", "", slow),))
        task = asyncio.create_task(runner.run())
        await started.wait()
        with self.assertRaises(RunAlreadyActive): await runner.run()
        self.assertTrue(await runner.cancel())
        report = await task
        self.assertEqual(report.results[0].status, Status.CANCELLED)

    async def test_bounded_parallelism(self) -> None:
        active = maximum = 0
        lock = asyncio.Lock()
        async def check():
            nonlocal active, maximum
            async with lock: active += 1; maximum = max(maximum, active)
            await asyncio.sleep(0.02)
            async with lock: active -= 1
            return True, "ok", ""
        runner = ScenarioRunner(tuple(Scenario(str(i), str(i), "smoke", "", "", check) for i in range(6)), max_parallel=2)
        await runner.run()
        self.assertLessEqual(maximum, 2)


class ReportingTests(unittest.TestCase):
    def test_markdown_json_bug_and_prompt(self) -> None:
        report = sample_report("token=supersecret")
        markdown = markdown_report(report)
        payload = json.loads(json_report(report))
        prompt = codex_prompt(report)
        combined = markdown + json.dumps(payload) + prompt
        self.assertNotIn("supersecret", combined)
        self.assertIn("Steps to reproduce", markdown)
        self.assertIn("Fix only the verified failures", prompt)

    def test_storage_is_path_safe_and_clear_is_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            storage = ReportStorage(root / "reports")
            markdown, json_path = storage.save(sample_report())
            unrelated = storage.directory / "keep.txt"
            unrelated.write_text("keep", encoding="utf-8")
            self.assertEqual(storage.last_markdown(), markdown)
            with self.assertRaises(ValueError): storage.safe_path("../crypto.db")
            self.assertEqual(storage.clear_reports(), 2)
            self.assertTrue(unrelated.exists())

    def test_exception_redaction(self) -> None:
        self.assertNotIn("secret", redact("api_key=secret"))


class QABoundaryTests(unittest.TestCase):
    def test_entrypoint_uses_separate_lock_and_no_main_token(self) -> None:
        source = Path("qa_bot/main.py").read_text(encoding="utf-8")
        config = Path("qa_bot/config.py").read_text(encoding="utf-8")
        self.assertIn(".crypto-hunter-qa.lock", source)
        self.assertNotIn('getenv("BOT_TOKEN"', source + config)
        self.assertNotIn("from main import", source)

    def test_generated_reports_are_ignored(self) -> None:
        ignore = Path(".gitignore").read_text(encoding="utf-8")
        self.assertIn("qa/reports/", ignore)
