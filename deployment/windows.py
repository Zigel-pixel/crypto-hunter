from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


@dataclass(frozen=True)
class InterpreterInfo:
    path: Path
    version: str


class LauncherAction(StrEnum):
    EXIT_NORMAL = "exit_normal"
    EXIT_DUPLICATE = "exit_duplicate"
    RESTART = "restart"
    EXIT_CRASH_LOOP = "exit_crash_loop"


def select_bootstrap_python(production_python: Path, configured_python: Path | None, launcher_python: Path | None, probe: Callable[[Path], str | None]) -> InterpreterInfo:
    for candidate in (production_python, configured_python, launcher_python):
        if candidate is None:
            continue
        version = probe(candidate)
        if version and version.startswith("Python "):
            return InterpreterInfo(candidate.resolve(), version)
    raise RuntimeError("No valid Python interpreter is available")


def resolve_restore_python(previous_pointer: Path | None, default_python: Path, exists: Callable[[Path], bool]) -> Path:
    if previous_pointer is not None and exists(previous_pointer):
        return previous_pointer.resolve()
    if exists(default_python):
        return default_python.resolve()
    raise RuntimeError("No valid rollback Python executable is available")


def launcher_action(exit_code: int, runtime_seconds: float, rapid_restarts: int, *, duplicate_exit_code: int = 1, rapid_window_seconds: int = 60, maximum_rapid_restarts: int = 3) -> LauncherAction:
    if exit_code == 0:
        return LauncherAction.EXIT_NORMAL
    if exit_code == duplicate_exit_code and runtime_seconds < 10:
        return LauncherAction.EXIT_DUPLICATE
    next_count = rapid_restarts + 1 if runtime_seconds < rapid_window_seconds else 0
    return LauncherAction.EXIT_CRASH_LOOP if next_count >= maximum_rapid_restarts else LauncherAction.RESTART
