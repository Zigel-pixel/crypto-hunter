from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum


class DeploymentStatus(StrEnum):
    NO_UPDATE = "no_update"
    VERIFIED = "verified"
    DEPLOYED = "deployed"
    DEPLOYED_WITH_E2E_FAILURES = "deployed_with_e2e_failures"
    BLOCKED = "blocked"
    ROLLED_BACK = "rolled_back"
    ROLLBACK_FAILED = "rollback_failed"
    NOTIFICATION_FAILED = "notification_failed"


class HealthStatus(StrEnum):
    HEALTHY = "healthy"
    FAILED_START = "failed_start"
    DUPLICATE_PROCESS = "duplicate_process"
    CRASH_LOOP = "crash_loop"
    TIMEOUT = "timeout"
    LOG_ERROR = "log_error"


@dataclass(frozen=True)
class StageResult:
    name: str
    passed: bool
    summary: str
    duration_seconds: float = 0.0


@dataclass(frozen=True)
class HealthResult:
    status: HealthStatus
    process_count: int
    summary: str

    @property
    def healthy(self) -> bool:
        return self.status is HealthStatus.HEALTHY


@dataclass(frozen=True)
class RollbackResult:
    source_restored: bool
    pointer_restored: bool
    processes_cleared: bool
    health_restored: bool

    @property
    def succeeded(self) -> bool:
        return all((self.source_restored, self.pointer_restored, self.processes_cleared, self.health_restored))

    @property
    def summary(self) -> str:
        return ", ".join(f"{name}={'ok' if value else 'failed'}" for name, value in (
            ("source", self.source_restored), ("pointer", self.pointer_restored),
            ("processes", self.processes_cleared), ("health", self.health_restored),
        ))


@dataclass
class DeploymentReport:
    branch: str
    old_commit: str
    new_commit: str
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    status: DeploymentStatus = DeploymentStatus.BLOCKED
    stages: list[StageResult] = field(default_factory=list)
    health: HealthResult | None = None
    smoke_e2e: str = "not_run"
    full_e2e: str = "not_run"
    rollback: str = "not_required"
    error: str = ""


@dataclass
class DeploymentState:
    last_checked_remote_commit: str = ""
    last_successfully_deployed_commit: str = ""
    previous_working_commit: str = ""
    failed_commit: str = ""
    last_deployment_timestamp: str = ""
    last_deployment_status: str = ""
    last_smoke_e2e_status: str = ""
    last_full_e2e_status: str = ""
    failure_count: int = 0
    last_notification_timestamp: str = ""
