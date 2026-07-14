from __future__ import annotations

from collections.abc import Callable
import os
from pathlib import Path

ReplaceExisting = Callable[[Path, Path, Path], None]


def atomic_replace(temporary: Path, destination: Path, replace_existing: ReplaceExisting | None = None) -> None:
    temporary = temporary.resolve()
    destination = destination.resolve()
    if temporary.parent != destination.parent:
        raise ValueError("Temporary and destination files must share a directory")
    if not temporary.is_file():
        raise FileNotFoundError("Atomic replacement temporary file is missing")
    backup = destination.with_name(destination.name + ".atomic-backup")
    succeeded = False
    try:
        if backup.exists():
            backup.unlink()
        if destination.exists():
            operation = replace_existing or _replace_existing
            operation(temporary, destination, backup)
        else:
            os.replace(temporary, destination)
        if not destination.is_file():
            raise OSError("Atomic replacement destination verification failed")
        succeeded = True
        if backup.exists():
            backup.unlink()
    except Exception:
        if backup.exists():
            try:
                if destination.exists():
                    destination.unlink()
                os.replace(backup, destination)
            except OSError as restore_error:
                raise OSError("Atomic replacement failed; original retained in backup") from restore_error
        raise
    finally:
        if not succeeded and temporary.exists():
            temporary.unlink()


def _replace_existing(temporary: Path, destination: Path, backup: Path) -> None:
    os.replace(destination, backup)
    try:
        os.replace(temporary, destination)
    except Exception:
        os.replace(backup, destination)
        raise
