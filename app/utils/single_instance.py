from __future__ import annotations

import fcntl
import os
from pathlib import Path
from types import TracebackType
from typing import IO


class InstanceAlreadyRunning(RuntimeError):
    """Raised when another local process owns the bot lock."""


class SingleInstanceLock:
    """Advisory process lock for local POSIX/macOS polling processes."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._file: IO[str] | None = None

    def acquire(self) -> None:
        lock_file = self._path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            lock_file.seek(0)
            owner = lock_file.read().strip() or "unknown"
            lock_file.close()
            raise InstanceAlreadyRunning(
                f"Crypto Hunter is already running locally (PID {owner})."
            ) from exc

        lock_file.seek(0)
        lock_file.truncate()
        lock_file.write(str(os.getpid()))
        lock_file.flush()
        self._file = lock_file

    def release(self) -> None:
        if self._file is None:
            return
        fcntl.flock(self._file.fileno(), fcntl.LOCK_UN)
        self._file.close()
        self._file = None

    def __enter__(self) -> SingleInstanceLock:
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.release()

