from __future__ import annotations

from dataclasses import asdict
import json
import os
from pathlib import Path
import tempfile

from app.utils.single_instance import SingleInstanceLock
from deployment.models import DeploymentState


class DeploymentStateStore:
    def __init__(self, path: Path, root: Path | None = None) -> None:
        self.path = path.resolve()
        self.root = (root or path.parent).resolve()
        if self.path.parent != self.root:
            raise ValueError("Deployment state must be directly inside its configured directory")

    def load(self) -> DeploymentState:
        if not self.path.exists():
            return DeploymentState()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("State must be an object")
            allowed = DeploymentState.__dataclass_fields__
            return DeploymentState(**{key: value for key, value in payload.items() if key in allowed})
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return DeploymentState()

    def save(self, state: DeploymentState) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix="deployment-state-", suffix=".tmp", dir=self.root)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(asdict(state), handle, indent=2, ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


def deployment_lock(path: Path) -> SingleInstanceLock:
    path.parent.mkdir(parents=True, exist_ok=True)
    return SingleInstanceLock(path)
