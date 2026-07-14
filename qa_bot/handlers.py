from __future__ import annotations

import asyncio
import logging

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.types import FSInputFile

from qa_bot.config import QAConfig
from qa_bot.keyboards import clear_confirmation_keyboard, main_keyboard
from qa_bot.models import RunReport, Status
from qa_bot.reporting import telegram_summary
from qa_bot.scenario_runner import RunAlreadyActive, ScenarioRunner
from qa_bot.security import is_authorized, safe_exception
from qa_bot.storage import ReportStorage

logger = logging.getLogger("crypto_hunter.qa")
SUITE_COMMANDS = {"run_all": "all", "run_smoke": "smoke", "run_localization": "localization", "run_live": "live", "run_favorites": "favorites", "run_alerts": "alerts", "run_ai": "ai", "run_wallets": "wallets"}
HELP = "Commands: /run_all /run_smoke /run_localization /run_live /run_favorites /run_alerts /run_ai /run_wallets /status /last_report /list_scenarios /cancel /clear_reports /codex_prompt"


async def authorize_event(event: types.Message | types.CallbackQuery, admin_id: int) -> bool:
    if is_authorized(event.from_user.id if event.from_user else None, admin_id):
        return True
    if isinstance(event, types.CallbackQuery):
        await event.answer("Access denied", show_alert=True)
    else:
        await event.answer("Access denied")
    return False


class QAController:
    def __init__(self, config: QAConfig, runner: ScenarioRunner, storage: ReportStorage) -> None:
        self.config, self.runner, self.storage = config, runner, storage
        self.last_report: RunReport | None = None
        self.run_task: asyncio.Task[None] | None = None

    async def start_run(self, message: types.Message, suite: str) -> None:
        if self.runner.running or (self.run_task and not self.run_task.done()):
            await message.answer("A QA run is already active. Use /cancel first.")
            return
        await message.answer(f"🧪 Crypto Hunter QA started\nSuite: {suite}")

        async def progress(done: int, total: int, result) -> None:
            if result.status in {Status.FAILED, Status.ERROR} or done == total:
                await message.answer(f"Completed: {done}/{total} · {result.status.value} · {result.title}")

        async def execute() -> None:
            try:
                report = await self.runner.run(suite, progress)
                self.last_report = report
                markdown, _ = self.storage.save(report)
                await message.answer(telegram_summary(report), reply_markup=main_keyboard())
                await message.answer_document(FSInputFile(markdown), caption=f"Report: {markdown.name}")
            except Exception as exc:
                kind, error = safe_exception(exc)
                logger.warning("QA run failed: %s: %s", kind, error)
                await message.answer(f"QA run could not complete ({kind}).")

        self.run_task = asyncio.create_task(execute())


def build_router(config: QAConfig, runner: ScenarioRunner, storage: ReportStorage) -> Router:
    router = Router(name="qa_bot")
    controller = QAController(config, runner, storage)

    async def authorized(event: types.Message | types.CallbackQuery) -> bool:
        return await authorize_event(event, config.admin_id)

    @router.message(Command("start", "help"))
    async def start(message: types.Message) -> None:
        if await authorized(message):
            await message.answer("🧪 Crypto Hunter internal QA\n\nThis runner tests services and mocks; it does not act as a Telegram user or click the production bot.\n\n" + HELP, reply_markup=main_keyboard())

    @router.message(Command(*SUITE_COMMANDS))
    async def run_command(message: types.Message) -> None:
        if not await authorized(message): return
        command = (message.text or "").split()[0].removeprefix("/").split("@", 1)[0]
        await controller.start_run(message, SUITE_COMMANDS[command])

    @router.callback_query(F.data.startswith("qa:run:"))
    async def run_callback(callback: types.CallbackQuery) -> None:
        if not await authorized(callback): return
        await callback.answer()
        if callback.message:
            await controller.start_run(callback.message, (callback.data or "").rsplit(":", 1)[1])

    @router.message(Command("status"))
    async def status(message: types.Message) -> None:
        if await authorized(message): await message.answer("QA run active." if runner.running else "QA runner idle.", reply_markup=main_keyboard())

    @router.callback_query(F.data == "qa:status")
    async def status_callback(callback: types.CallbackQuery) -> None:
        if await authorized(callback): await callback.answer("QA run active" if runner.running else "QA runner idle", show_alert=True)

    @router.message(Command("list_scenarios"))
    async def list_scenarios(message: types.Message) -> None:
        if await authorized(message): await message.answer("\n".join(f"• {item.id} — {item.title}" for item in runner.scenarios))

    @router.message(Command("cancel"))
    async def cancel(message: types.Message) -> None:
        if await authorized(message): await message.answer("Cancellation requested." if await runner.cancel() else "No QA run is active.")

    @router.callback_query(F.data == "qa:cancel")
    async def cancel_callback(callback: types.CallbackQuery) -> None:
        if await authorized(callback): await callback.answer("Cancellation requested" if await runner.cancel() else "No active QA run", show_alert=True)

    async def send_last(message: types.Message) -> None:
        path = storage.last_markdown()
        if path is None: await message.answer("No generated report is available.")
        else: await message.answer_document(FSInputFile(path), caption=path.name)

    @router.message(Command("last_report"))
    async def last_report(message: types.Message) -> None:
        if await authorized(message): await send_last(message)

    @router.callback_query(F.data == "qa:last")
    async def last_callback(callback: types.CallbackQuery) -> None:
        if not await authorized(callback): return
        await callback.answer()
        if callback.message: await send_last(callback.message)

    async def send_prompt(message: types.Message) -> None:
        if controller.last_report is None: await message.answer("Run QA first; no in-memory report is available for prompt generation.")
        else:
            path = storage.save_codex_prompt(controller.last_report)
            await message.answer_document(FSInputFile(path), caption="Verified failures only. This file does not invoke Codex.")

    @router.message(Command("codex_prompt"))
    async def prompt(message: types.Message) -> None:
        if await authorized(message): await send_prompt(message)

    @router.callback_query(F.data == "qa:prompt")
    async def prompt_callback(callback: types.CallbackQuery) -> None:
        if not await authorized(callback): return
        await callback.answer()
        if callback.message: await send_prompt(callback.message)

    @router.message(Command("clear_reports"))
    async def clear_reports(message: types.Message) -> None:
        if await authorized(message): await message.answer("Clear only generated QA reports?", reply_markup=clear_confirmation_keyboard())

    @router.callback_query(F.data.startswith("qa:clear:"))
    async def clear_callback(callback: types.CallbackQuery) -> None:
        if not await authorized(callback): return
        await callback.answer()
        if callback.message:
            if callback.data == "qa:clear:confirm": await callback.message.answer(f"Cleared {storage.clear_reports()} generated report files.")
            else: await callback.message.answer("Clear cancelled.")

    return router
