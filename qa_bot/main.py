from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from aiogram import Bot, Dispatcher

from qa import all_scenarios
from qa_bot.config import QAConfigError, load_qa_config
from qa_bot.handlers import build_router
from qa_bot.scenario_runner import ScenarioRunner
from qa_bot.storage import ReportStorage
from app.utils.single_instance import InstanceAlreadyRunning, SingleInstanceLock

QA_LOCK_FILE = Path(__file__).resolve().parent.parent / ".crypto-hunter-qa.lock"


async def main() -> None:
    config = load_qa_config()
    bot = Bot(token=config.token)
    dispatcher = Dispatcher()
    runner = ScenarioRunner(all_scenarios(), timeout=config.scenario_timeout, max_parallel=config.max_parallel, real_provider_checks=config.real_provider_checks)
    dispatcher.include_router(build_router(config, runner, ReportStorage(config.reports_dir)))
    try:
        await dispatcher.start_polling(bot)
    finally:
        await runner.cancel()
        await bot.session.close()


def run() -> int:
    try:
        with SingleInstanceLock(QA_LOCK_FILE):
            asyncio.run(main())
    except (QAConfigError, InstanceAlreadyRunning) as exc:
        logging.getLogger("crypto_hunter.qa").error("QA bot could not start: %s", type(exc).__name__)
        return 1
    return 0
