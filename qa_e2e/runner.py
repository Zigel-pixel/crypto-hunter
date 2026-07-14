from __future__ import annotations

from dataclasses import replace
import platform

from qa_bot.models import RunReport, Status
from qa_bot.scenario_runner import ScenarioRunner
from qa_e2e.client import TelegramE2EClient
from qa_e2e.config import E2EConfig
from qa_e2e.scenarios import build_scenarios


class E2ERunner:
    def __init__(self, config: E2EConfig, client: TelegramE2EClient | None = None) -> None:
        self.config = config
        self.client = client or TelegramE2EClient(config)
        self.runner = ScenarioRunner(build_scenarios(self.client, config), timeout=config.max_scenario_seconds, max_parallel=1, real_provider_checks=True)

    async def run(self, suite: str) -> RunReport:
        await self.client.connect()
        try:
            report = await self.runner.run(suite)
            try:
                import telethon
                version = telethon.__version__
            except ImportError:
                version = "unavailable"
            environment = f"{platform.system()} · Python {platform.python_version()} · Telethon {version} · language={self.config.test_language} · destructive={self.config.allow_destructive} · real target bot interaction"
            return replace(report, run_type=f"Telegram E2E: {suite}", environment=environment)
        finally:
            await self.client.disconnect()

    async def cancel(self) -> bool:
        return await self.runner.cancel()


def exit_code(report: RunReport) -> int:
    return 1 if any(item.status in {Status.FAILED, Status.ERROR, Status.CANCELLED} for item in report.results) else 0
