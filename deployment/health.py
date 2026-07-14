from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from deployment.models import HealthResult, HealthStatus


@dataclass(frozen=True)
class ProcessInfo:
    pid: int
    command_line: str


def evaluate_health(processes: Iterable[ProcessInfo], production_dir: Path, log_tail: str, *, remained_alive: bool = True) -> HealthResult:
    root = str(production_dir.resolve()).casefold()
    matching = tuple(item for item in processes if root in item.command_line.casefold() and "main.py" in item.command_line.casefold())
    if not matching:
        return HealthResult(HealthStatus.FAILED_START, 0, "Production bot process was not found")
    if len(matching) != 1:
        return HealthResult(HealthStatus.DUPLICATE_PROCESS, len(matching), "Multiple matching production bot processes were found")
    normalized = log_tail.casefold()
    if normalized.count("starting crypto hunter") >= 3:
        return HealthResult(HealthStatus.CRASH_LOOP, 1, "Repeated startup entries detected")
    if "traceback (most recent call last)" in normalized:
        return HealthResult(HealthStatus.LOG_ERROR, 1, "Immediate traceback detected")
    if not remained_alive:
        return HealthResult(HealthStatus.TIMEOUT, 1, "Bot did not remain alive for the health window")
    startup_markers = ("start_polling", "polling", "run_polling", "starting crypto hunter")
    if not any(marker in normalized for marker in startup_markers):
        return HealthResult(HealthStatus.TIMEOUT, 1, "Polling startup marker was not observed")
    return HealthResult(HealthStatus.HEALTHY, 1, "Exactly one production bot process is healthy")
