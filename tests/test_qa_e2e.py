from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, Mock, patch
from telethon.tl import types as tl_types

from qa_bot.models import RunReport, ScenarioResult, Severity, Status
from qa_e2e.auth import authorize
from qa_e2e.client import TargetNotBot, TelegramE2EClient
from qa_e2e.config import E2EConfig, E2EConfigError, load_e2e_config
from qa_e2e.evidence import sanitize_text
from qa_e2e.models import ActionResult, MessageEvidence
from qa_e2e.selectors import UnsafeButtonError, button_labels, find_inline_button, reply_keyboard_labels, select_reply_label
from qa_e2e.scenarios.flows import _latest_reply_keyboard, _start_and_open
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
        safe = tl_types.KeyboardButtonCallback("Refresh", b"rates:live:refresh")
        markup = tl_types.ReplyInlineMarkup([tl_types.KeyboardButtonRow([safe])])
        message = Mock(buttons=[[safe]], reply_markup=markup)
        self.assertIs(find_inline_button(message, callback_prefix="rates:live:"), safe)
        unsafe = tl_types.KeyboardButtonUrl("Pay", "https://example.com")
        unsafe_markup = tl_types.ReplyInlineMarkup([tl_types.KeyboardButtonRow([unsafe])])
        with self.assertRaises(UnsafeButtonError): find_inline_button(Mock(buttons=[[unsafe]], reply_markup=unsafe_markup), text="Pay")

    def test_reply_selector_normalizes(self) -> None:
        button = tl_types.KeyboardButton("  📈 Rates ")
        message = Mock(reply_markup=tl_types.ReplyKeyboardMarkup([tl_types.KeyboardButtonRow([button])]))
        self.assertEqual(select_reply_label(message, ("📈 rates",)), "  📈 Rates ")

    def test_markup_types_never_cross_classify_same_text(self) -> None:
        reply_button = tl_types.KeyboardButton("Same")
        reply = Mock(reply_markup=tl_types.ReplyKeyboardMarkup([tl_types.KeyboardButtonRow([reply_button])]), buttons=[[reply_button]])
        inline_button = tl_types.KeyboardButtonCallback("Same", b"safe:action")
        inline = Mock(reply_markup=tl_types.ReplyInlineMarkup([tl_types.KeyboardButtonRow([inline_button])]), buttons=[[inline_button]])
        self.assertEqual(reply_keyboard_labels(reply), ("Same",))
        self.assertEqual(button_labels(reply), ())
        self.assertEqual(reply_keyboard_labels(inline), ())
        self.assertEqual(button_labels(inline), ("Same",))

    def test_hide_and_force_reply_have_no_buttons(self) -> None:
        for markup in (tl_types.ReplyKeyboardHide(), tl_types.ReplyKeyboardForceReply()):
            message = Mock(reply_markup=markup, buttons=None)
            self.assertEqual(reply_keyboard_labels(message), ())
            self.assertEqual(button_labels(message), ())


class FakeMessages(list):
    pass


class E2EClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_feature_suite_setup_always_starts_before_resolving_menu_action(self) -> None:
        for candidates in (
            ("🤖 AI Консультант", "🤖 AI Consultant"),
            ("⭐ Обране", "⭐ Watchlist"),
            ("📈 Курси", "📈 Rates"),
            ("👛 Гаманці", "👛 Wallets"),
        ):
            client = Mock()
            client.send = AsyncMock(return_value=Mock(messages=(Mock(),)))
            client.send_recent_reply_action = AsyncMock(return_value="opened")
            self.assertEqual(await _start_and_open(client, candidates), "opened")
            client.send.assert_awaited_once_with("/start")
            client.send_recent_reply_action.assert_awaited_once_with(candidates)

    async def test_recent_actions_skip_newer_non_owning_messages(self) -> None:
        wrapper = TelegramE2EClient(config(), AsyncMock()); wrapper.target = Mock(id=100)
        inline_button = tl_types.KeyboardButtonCallback("Live", b"rates:live:start")
        inline = Mock(buttons=[[inline_button]], reply_markup=tl_types.ReplyInlineMarkup([tl_types.KeyboardButtonRow([inline_button])]))
        no_buttons = Mock(buttons=None, reply_markup=None)
        reply_button = tl_types.KeyboardButton("🌐 Мова")
        reply = Mock(id=9, date=None, out=False,
                     reply_markup=tl_types.ReplyKeyboardMarkup([tl_types.KeyboardButtonRow([reply_button])]), buttons=None)
        wrapper.last_raw_messages = (inline, reply, no_buttons)
        wrapper._process_reply_keyboard(reply)
        wrapper.click_inline = AsyncMock(return_value="clicked")
        wrapper.send = AsyncMock(return_value="sent")
        self.assertEqual(await wrapper.click_recent_inline(callback_prefix="rates:live:start"), "clicked")
        self.assertIs(wrapper.click_inline.await_args.args[0], inline)
        self.assertEqual(await wrapper.send_recent_reply_action(("🌐 Мова", "🌐 Language")), "sent")
        wrapper.send.assert_awaited_once_with("🌐 Мова", timeout=None)

    async def test_reply_keyboard_persists_until_hidden_and_ignores_inline_force_plain(self) -> None:
        wrapper = TelegramE2EClient(config(), AsyncMock()); wrapper.target = Mock(id=100)
        reply_button = tl_types.KeyboardButton("📈 Курси")
        reply = Mock(id=10, date=datetime.now(timezone.utc), out=False,
                     reply_markup=tl_types.ReplyKeyboardMarkup([tl_types.KeyboardButtonRow([reply_button])]))
        wrapper._process_reply_keyboard(reply)
        self.assertEqual(wrapper.active_reply_keyboard.labels, ("📈 Курси",))
        inline_button = tl_types.KeyboardButtonCallback("📈 Курси", b"rates:inline")
        for message in (
            Mock(id=11, out=False, reply_markup=None),
            Mock(id=12, out=False, reply_markup=tl_types.ReplyInlineMarkup([tl_types.KeyboardButtonRow([inline_button])])),
            Mock(id=13, out=False, reply_markup=tl_types.ReplyKeyboardForceReply()),
        ):
            wrapper._process_reply_keyboard(message)
            self.assertEqual(wrapper.active_reply_keyboard.labels, ("📈 Курси",))
        wrapper._process_reply_keyboard(Mock(id=14, out=False, reply_markup=tl_types.ReplyKeyboardHide()))
        self.assertIsNone(wrapper.active_reply_keyboard)

    async def test_newest_keyboard_replaces_old_and_state_is_target_scoped(self) -> None:
        wrapper = TelegramE2EClient(config(), AsyncMock()); wrapper.target = Mock(id=100)
        def message(message_id, label):
            button = tl_types.KeyboardButton(label)
            return Mock(id=message_id, date=None, out=False, reply_markup=tl_types.ReplyKeyboardMarkup([tl_types.KeyboardButtonRow([button])]))
        wrapper._process_reply_keyboard(message(1, "📈 Rates"))
        wrapper._process_reply_keyboard(message(2, "⭐ Watchlist"))
        self.assertEqual(wrapper.active_reply_keyboard.labels, ("⭐ Watchlist",))
        wrapper.target = Mock(id=200)
        self.assertIsNone(wrapper.active_reply_keyboard)
        wrapper._process_reply_keyboard(message(3, "👛 Гаманці"))
        self.assertEqual(wrapper.active_reply_keyboard.labels, ("👛 Гаманці",))
        wrapper.target = Mock(id=100)
        self.assertEqual(wrapper.active_reply_keyboard.source_message_id, 2)

    async def test_english_and_ukrainian_actions_resolve_from_persistent_state(self) -> None:
        for target_id, label, candidates in (
            (1, "🤖 AI Consultant", ("🤖 AI Consultant", "🤖 AI Консультант")),
            (2, "👛 Гаманці", ("👛 Wallets", "👛 Гаманці")),
        ):
            wrapper = TelegramE2EClient(config(), AsyncMock()); wrapper.target = Mock(id=target_id)
            button = tl_types.KeyboardButton(label)
            message = Mock(id=5, date=None, out=False,
                           reply_markup=tl_types.ReplyKeyboardMarkup([tl_types.KeyboardButtonRow([button])]))
            wrapper._process_reply_keyboard(message)
            wrapper.send = AsyncMock(return_value="sent")
            self.assertEqual(await wrapper.send_recent_reply_action(candidates), "sent")
            wrapper.send.assert_awaited_once_with(label, timeout=None)

    async def test_keyboard_error_evidence_is_redacted(self) -> None:
        wrapper = TelegramE2EClient(config(), AsyncMock()); wrapper.target = Mock(id=1)
        button = tl_types.KeyboardButton("phone +1 202 555 0123")
        message = Mock(id=77, date=None, out=False,
                       reply_markup=tl_types.ReplyKeyboardMarkup([tl_types.KeyboardButtonRow([button])]))
        wrapper._process_reply_keyboard(message)
        with self.assertRaises(LookupError) as context:
            await wrapper.send_recent_reply_action(("📈 Rates",))
        self.assertIn("source_message=77", str(context.exception))
        self.assertNotIn("202", str(context.exception))

    async def test_recent_history_initializes_persistent_keyboard_state(self) -> None:
        raw = AsyncMock()
        button = tl_types.KeyboardButton("⭐ Обране")
        owner = Mock(id=20, date=datetime.now(timezone.utc), out=False,
                     reply_markup=tl_types.ReplyKeyboardMarkup([tl_types.KeyboardButtonRow([button])]))
        later_plain = Mock(id=21, date=datetime.now(timezone.utc), out=False, reply_markup=None)
        raw.get_messages.return_value = [later_plain, owner]
        wrapper = TelegramE2EClient(config(), raw); wrapper.target = Mock(id=500)
        await wrapper._refresh_reply_keyboard_state()
        self.assertEqual(wrapper.active_reply_keyboard.labels, ("⭐ Обране",))
        self.assertEqual(wrapper.active_reply_keyboard.source_message_id, 20)
        raw.get_messages.assert_awaited_once_with(wrapper.target, limit=50)

    async def test_ukrainian_start_uses_newest_fresh_reply_keyboard(self) -> None:
        stale = MessageEvidence(1, None, "old", None, (), ("📈 Rates",), 0.1)
        inline = MessageEvidence(2, None, "inline", None, ("📈 Курси",), (), 0.2)
        current = MessageEvidence(3, None, "Ваш сеанс активний", None, (), ("📈 Курси", "⚙ Налаштування"), 0.3)
        result = ActionResult("/start", 1, (stale, inline, current), 0.1, 0.4)
        self.assertIs(_latest_reply_keyboard(result, ("📈 Rates", "📈 Курси")), current)

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
        for pattern in ("*.session", "*.session-journal", "qa/e2e_sessions/", "qa/e2e_reports/", "qa/e2e_artifacts/", ".crypto-hunter-e2e.lock"):
            self.assertIn(pattern, ignore)
