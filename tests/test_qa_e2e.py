from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, Mock, patch

from qa_bot.models import RunReport, ScenarioResult, Severity, Status
from qa_e2e.auth import authorize
from qa_e2e.client import TargetNotBot, TelegramE2EClient
from qa_e2e.config import E2EConfig, E2EConfigError, load_e2e_config
from qa_e2e.evidence import sanitize_text
from qa_e2e.selectors import UnsafeButtonError, find_inline_button, select_reply_label
from qa_e2e.storage import ARTIFACT_RE, E2EStorage, REPORT_RE


BASE_ENV = {
    "E2E_ENABLED": "true", "E2E_TELEGRAM_API_ID": "12345", "E2E_TELEGRAM_API_HASH": "hash",
    "E2E_TELEGRAM_PHONE": "+10000000000", "E2E_TARGET_BOT_USERNAME": "CryptoHunterTestBot",
    "E2E_SESSION_PATH": "qa/e2e_sessions/test", "E2E_REPORTS_DIR": "qa/e2e_reports",
    "E2E_ARTIFACTS_DIR": "qa/e2e_artifacts",
}


def config(tmp: Path | None = None) -> E2EConfig:
    root = tmp or Path("qa/e2e_artifacts")
    return E2EConfig(True, 1, "hash", "+10000000000", "CryptoHunterTestBot", Path("qa/e2e_sessions/test"), root / "reports", root / "artifacts", settle_seconds=1)


class E2EConfigTests(unittest.TestCase):
    def test_disabled_by_default(self) -> None:
        with patch.dict(os.environ, BASE_ENV | {"E2E_ENABLED": "false"}, clear=True):
            with self.assertRaises(E2EConfigError): load_e2e_config(load_env_file=False)

    def test_invalid_required_values(self) -> None:
        for name, value in (("E2E_TELEGRAM_API_ID", "bad"), ("E2E_TELEGRAM_API_HASH", ""), ("E2E_TELEGRAM_PHONE", ""), ("E2E_TARGET_BOT_USERNAME", "x")):
            with self.subTest(name=name), patch.dict(os.environ, BASE_ENV | {name: value}, clear=True):
                with self.assertRaises(E2EConfigError): load_e2e_config(load_env_file=False)

    def test_paths_cannot_escape(self) -> None:
        with patch.dict(os.environ, BASE_ENV | {"E2E_SESSION_PATH": "../stolen"}, clear=True):
            with self.assertRaises(E2EConfigError): load_e2e_config(load_env_file=False)

    def test_username_normalizes_at_and_destructive_defaults_false(self) -> None:
        with patch.dict(os.environ, BASE_ENV | {"E2E_TARGET_BOT_USERNAME": "@CryptoHunterTestBot"}, clear=True):
            value = load_e2e_config(load_env_file=False)
        self.assertEqual(value.target_username, "CryptoHunterTestBot")
        self.assertFalse(value.allow_destructive)


class SelectorTests(unittest.TestCase):
    def test_inline_selector_and_forbidden_controls(self) -> None:
        safe = Mock(text="Refresh", data=b"rates:live:refresh", url=None, login_url=None, webview=None, web_app=None, buy=False, payment=False)
        message = Mock(buttons=[[safe]])
        self.assertIs(find_inline_button(message, callback_prefix="rates:live:"), safe)
        unsafe = Mock(text="Pay", data=b"pay", url="https://example.com", login_url=None, webview=None, web_app=None, buy=False, payment=False)
        with self.assertRaises(UnsafeButtonError): find_inline_button(Mock(buttons=[[unsafe]]), text="Pay")

    def test_reply_selector_normalizes(self) -> None:
        button = Mock(text="  📈 Rates ")
        message = Mock(reply_markup=Mock(rows=[Mock(buttons=[button])]))
        self.assertEqual(select_reply_label(message, ("📈 rates",)), "  📈 Rates ")


class FakeMessages(list):
    pass


class E2EClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_target_must_be_bot(self) -> None:
        raw = AsyncMock()
        raw.is_user_authorized.return_value = True
        raw.get_entity.return_value = Mock(bot=False, username="CryptoHunterTestBot")
        wrapper = TelegramE2EClient(config(), raw)
        with self.assertRaises(TargetNotBot): await wrapper.connect()

    async def test_collection_is_bounded_to_target_and_baseline(self) -> None:
        raw = AsyncMock()
        wrapper = TelegramE2EClient(config(), raw); wrapper.target = Mock()
        old = Mock(id=4, message="old", media=None, date=datetime.now(timezone.utc), edit_date=None, buttons=None, reply_markup=None)
        new = Mock(id=6, message="hello", media=None, date=datetime.now(timezone.utc), edit_date=None, buttons=None, reply_markup=None)
        raw.get_messages.return_value = [new, old]
        with patch("qa_e2e.client.asyncio.sleep", AsyncMock()):
            result = await wrapper.collect(5, "test", time.monotonic(), timeout=1)
        self.assertEqual([item.message_id for item in result.messages], [6])
        raw.get_messages.assert_awaited()
        self.assertIs(raw.get_messages.call_args.args[0], wrapper.target)

    async def test_authorization_uses_secure_password_reader(self) -> None:
        class SessionPasswordNeededError(Exception): pass
        raw = AsyncMock()
        raw.is_user_authorized.side_effect = [False, True]
        raw.send_code_request.return_value = Mock(phone_code_hash="x")
        raw.sign_in.side_effect = [SessionPasswordNeededError(), None]
        code_reader, password_reader = Mock(return_value="12345"), Mock(return_value="secret-password")
        self.assertTrue(await authorize(config(), client=raw, code_reader=code_reader, password_reader=password_reader))
        code_reader.assert_called_once()
        password_reader.assert_called_once()
        raw.disconnect.assert_awaited_once()


class E2EStorageTests(unittest.TestCase):
    def test_reports_and_cleanup_are_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); storage = E2EStorage(root / "reports", root / "artifacts")
            now = datetime.now(timezone.utc)
            result = ScenarioResult("x", "x", "smoke", now, now, 0, Status.PASSED, Severity.LOW, "yes", "yes")
            report = RunReport("Telegram E2E: smoke", now, now, "branch", "commit", "safe", (result,))
            markdown, json_path, prompt = storage.save(report)
            self.assertTrue(REPORT_RE.fullmatch(markdown.name)); self.assertIsNone(prompt)
            keep = storage.reports_dir / "keep.txt"; keep.write_text("keep", encoding="utf-8")
            self.assertEqual(storage.clear_reports(), 2); self.assertTrue(keep.exists())
            with self.assertRaises(ValueError): storage.safe_filename("../x.session", (REPORT_RE,))

    def test_evidence_redacts_phone_and_secrets(self) -> None:
        text = sanitize_text("phone +1 202 555 0123 api_key=supersecret")
        self.assertNotIn("202", text); self.assertNotIn("supersecret", text)

    def test_structured_public_values_are_not_corrupted(self) -> None:
        evm = "0x000000000000000000000000000000000000dEaD"
        tron = "TXLAQ63Xg1NAzckPwKHvzw7CSEmLMEqcdj"
        tx_hash = "0x" + "a1" * 32
        text = sanitize_text(f"{evm} {tron} {tx_hash} price=12345678.90 id=123456789 at=2026-07-14 12:30:00")
        self.assertIn("0x0000…dEaD", text)
        self.assertIn("TXLAQ6…qcdj", text)
        self.assertIn(tx_hash, text)
        self.assertIn("12345678.90", text)
        self.assertIn("123456789", text)
        self.assertIn("2026-07-14 12:30:00", text)

    def test_configured_phone_and_api_credentials_are_redacted(self) -> None:
        env = {"E2E_TELEGRAM_PHONE": "380501234567", "E2E_TELEGRAM_API_ID": "12345678", "E2E_TELEGRAM_API_HASH": "abcdef123456"}
        with patch.dict(os.environ, env, clear=False):
            text = sanitize_text("380501234567 12345678 abcdef123456")
        for secret in env.values():
            self.assertNotIn(secret, text)


class E2EBoundaryTests(unittest.TestCase):
    def test_no_main_or_qa_bot_tokens_and_no_shell_execution(self) -> None:
        sources = "\n".join(path.read_text(encoding="utf-8") for path in Path("qa_e2e").rglob("*.py"))
        self.assertNotIn('getenv("BOT_TOKEN"', sources)
        self.assertNotIn('getenv("QA_BOT_TOKEN"', sources)
        self.assertNotIn("subprocess", sources)
        self.assertNotIn("os.system", sources)

    def test_sensitive_artifacts_are_ignored(self) -> None:
        ignore = Path(".gitignore").read_text(encoding="utf-8")
        for pattern in ("*.session", "*.session-journal", "qa/e2e_sessions/", "qa/e2e_reports/", "qa/e2e_artifacts/"):
            self.assertIn(pattern, ignore)
