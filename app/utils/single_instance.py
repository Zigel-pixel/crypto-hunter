from __future__ import annotations

import os
from pathlib import Path
from types import TracebackType
from typing import IO

if os.name == "nt":
    import msvcrt
else:
    import fcntl


class InstanceAlreadyRunning(RuntimeError):
    """Raised when another local process owns the bot lock."""


class SingleInstanceLock:
    """Cross-platform advisory process lock for local polling processes."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._file: IO[str] | None = None

    def acquire(self) -> None:
        lock_file = self._path.open("a+", encoding="utf-8")

        try:
            if os.name == "nt":
                # Windows locking requires at least one byte in the file.
                lock_file.seek(0)
                if not lock_file.read(1):
                    lock_file.seek(0)
                    lock_file.write("0")
                    lock_file.flush()

                lock_file.seek(0)
                msvcrt.locking(
                    lock_file.fileno(),
                    msvcrt.LK_NBLCK,
                    1,
                )
            else:
                fcntl.flock(
                    lock_file.fileno(),
                    fcntl.LOCK_EX | fcntl.LOCK_NB,
                )

        except (BlockingIOError, OSError) as exc:
            owner = "unknown"
            try:
                lock_file.seek(0)
                owner = lock_file.read().strip() or owner
            except OSError:
                # Windows may deny reads from the byte range held by the owner.
                pass
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

        try:
            if os.name == "nt":
                self._file.seek(0)
                msvcrt.locking(
                    self._file.fileno(),
                    msvcrt.LK_UNLCK,
                    1,
                )
            else:
                fcntl.flock(
                    self._file.fileno(),
                    fcntl.LOCK_UN,
                )
        finally:
            self._file.close()
            self._file = None

    def __enter__(self) -> "SingleInstanceLock":
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.release()
