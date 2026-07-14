from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
import re

from deployment.models import HealthResult, HealthStatus


@dataclass(frozen=True)
class ProcessInfo:
    pid: int
    command_line: str
    parent_pid: int | None = None
    executable_path: str = ""


@dataclass(frozen=True)
class LogicalProcessInstance:
    root: ProcessInfo
    processes: tuple[ProcessInfo, ...]
    expected_root: bool


def matches_production_process(process: ProcessInfo, production_dir: Path) -> bool:
    expected = str(production_dir.resolve() / "main.py").replace("/", "\\").casefold()
    command = process.command_line.replace("/", "\\").casefold()
    return bool(re.search(rf'(^|\s|"){re.escape(expected)}($|\s|")', command))


def matching_production_processes(processes: Iterable[ProcessInfo], production_dir: Path) -> tuple[ProcessInfo, ...]:
    return tuple(item for item in processes if matches_production_process(item, production_dir))


def logical_production_instances(
    processes: Iterable[ProcessInfo], production_dir: Path, expected_python: Path | None = None
) -> tuple[LogicalProcessInstance, ...]:
    matching = matching_production_processes(processes, production_dir)
    by_pid = {item.pid: item for item in matching}
    children: dict[int, list[ProcessInfo]] = {}
    for item in matching:
        if item.parent_pid in by_pid:
            children.setdefault(item.parent_pid, []).append(item)
    roots = tuple(item for item in matching if item.parent_pid not in by_pid)
    expected = _normalized_path(expected_python) if expected_python else None
    instances = []
    for root in roots:
        tree: list[ProcessInfo] = []
        pending = [root]
        while pending:
            current = pending.pop()
            tree.append(current)
            pending.extend(children.get(current.pid, ()))
        root_path = _normalized_path(Path(root.executable_path)) if root.executable_path else None
        instances.append(LogicalProcessInstance(root, tuple(tree), expected is None or root_path == expected))
    return tuple(instances)


def _normalized_path(path: Path) -> str:
    return str(path.resolve()).replace("/", "\\").casefold()


def evaluate_health(
    processes: Iterable[ProcessInfo], production_dir: Path, log_tail: str, *,
    remained_alive: bool = True, expected_python: Path | None = None,
) -> HealthResult:
    instances = logical_production_instances(processes, production_dir, expected_python)
    if not instances:
        return HealthResult(HealthStatus.FAILED_START, 0, "Production bot process was not found")
    if len(instances) != 1:
        return HealthResult(HealthStatus.DUPLICATE_PROCESS, len(instances), "Multiple production bot process trees were found")
    if not instances[0].expected_root:
        return HealthResult(HealthStatus.FAILED_START, 1, "Production bot root executable does not match active Python")
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
    return HealthResult(HealthStatus.HEALTHY, 1, "Exactly one production bot process tree is healthy")
