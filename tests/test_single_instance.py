from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.utils.single_instance import InstanceAlreadyRunning, SingleInstanceLock


class SingleInstanceLockTests(unittest.TestCase):
    def test_lock_blocks_second_owner_and_can_be_reacquired(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bot.lock"
            first = SingleInstanceLock(path)
            second = SingleInstanceLock(path)
            first.acquire()
            try:
                with self.assertRaises(InstanceAlreadyRunning):
                    second.acquire()
            finally:
                first.release()

            second.acquire()
            second.release()

    def test_release_without_acquire_is_safe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            SingleInstanceLock(Path(directory) / "bot.lock").release()


if __name__ == "__main__":
    unittest.main()
