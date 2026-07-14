from __future__ import annotations

import asyncio
import os
import platform
import subprocess
import time
from collections.abc import Awaitable, Callable, Iterable
from datetime import datetime, timezone

from qa_bot.models import RunReport, Scenario, ScenarioResult, Severity, Status
from qa_bot.security import safe_exception

Progress = Callable[[int, int, ScenarioResult], Awaitable[None]]


class RunAlreadyActive(RuntimeError):
    pass


class ScenarioRunner:
    def __init__(self, scenarios: Iterable[Scenario], *, timeout: int = 60, max_parallel: int = 3, real_provider_checks: bool = False) -> None:
        self.scenarios = tuple(sorted(scenarios, key=lambda item: item.id))
        self.timeout = timeout
        self.max_parallel = max_parallel
        self.real_provider_checks = real_provider_checks
        self._active_task: asyncio.Task[RunReport] | None = None
        self._cancel_event = asyncio.Event()

    @property
    def running(self) -> bool:
        return self._active_task is not None and not self._active_task.done()

    def for_suite(self, suite: str) -> tuple[Scenario, ...]:
        return self.scenarios if suite == "all" else tuple(item for item in self.scenarios if item.suite == suite)

    async def run(self, suite: str = "all", progress: Progress | None = None) -> RunReport:
        if self.running:
            raise RunAlreadyActive("A QA run is already active")
        self._cancel_event = asyncio.Event()
        task = asyncio.create_task(self._run(suite, progress))
        self._active_task = task
        try:
            return await task
        finally:
            if self._active_task is task:
                self._active_task = None

    async def cancel(self) -> bool:
        if not self.running:
            return False
        self._cancel_event.set()
        return True

    async def _run(self, suite: str, progress: Progress | None) -> RunReport:
        selected = self.for_suite(suite)
        started = datetime.now(timezone.utc)
        semaphore = asyncio.Semaphore(self.max_parallel)
        completed = 0
        lock = asyncio.Lock()

        async def execute(scenario: Scenario) -> ScenarioResult:
            nonlocal completed
            async with semaphore:
                result = await self._execute(scenario)
            async with lock:
                completed += 1
                if progress:
                    await progress(completed, len(selected), result)
            return result

        results = await asyncio.gather(*(execute(item) for item in selected))
        return RunReport(suite, started, datetime.now(timezone.utc), _git("branch"), _git("commit"), f"{platform.system()} · Python {platform.python_version()}", tuple(results))

    async def _execute(self, scenario: Scenario) -> ScenarioResult:
        started = datetime.now(timezone.utc)
        clock = time.monotonic()
        status = Status.ERROR
        actual = "Scenario did not complete"
        details = ""
        exception_type = error_message = None
        if self._cancel_event.is_set():
            status, actual = Status.CANCELLED, "QA run cancelled"
        elif scenario.requires_real_provider and not self.real_provider_checks:
            status, actual = Status.SKIPPED, "Real-provider checks are disabled"
        else:
            try:
                check_task = asyncio.create_task(scenario.check())
                cancel_task = asyncio.create_task(self._cancel_event.wait())
                done, _ = await asyncio.wait((check_task, cancel_task), timeout=scenario.timeout or self.timeout, return_when=asyncio.FIRST_COMPLETED)
                if cancel_task in done and self._cancel_event.is_set():
                    check_task.cancel()
                    await asyncio.gather(check_task, return_exceptions=True)
                    status, actual = Status.CANCELLED, "QA run cancelled"
                elif check_task in done:
                    cancel_task.cancel()
                    await asyncio.gather(cancel_task, return_exceptions=True)
                    passed, actual, details = await check_task
                    status = Status.PASSED if passed else Status.FAILED
                else:
                    check_task.cancel(); cancel_task.cancel()
                    await asyncio.gather(check_task, cancel_task, return_exceptions=True)
                    status, actual, exception_type = Status.ERROR, "Scenario timed out", "TimeoutError"
            except asyncio.TimeoutError:
                status, actual, exception_type = Status.ERROR, "Scenario timed out", "TimeoutError"
            except asyncio.CancelledError:
                status, actual = Status.CANCELLED, "Scenario cancelled"
            except Exception as exc:
                exception_type, error_message = safe_exception(exc)
                actual = error_message
        finished = datetime.now(timezone.utc)
        return ScenarioResult(scenario.id, scenario.title, scenario.suite, started, finished, time.monotonic() - clock, status, scenario.severity, scenario.expected, actual, details, exception_type=exception_type, error_message=error_message, related_modules=scenario.related_modules, reproduction_steps=scenario.reproduction_steps, recommended_investigation=scenario.recommended_investigation)


def _git(kind: str) -> str:
    args = ["git", "branch", "--show-current"] if kind == "branch" else ["git", "rev-parse", "--short", "HEAD"]
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=2, check=True).stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"
