from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class Status(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"
    CANCELLED = "cancelled"


class Severity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


ScenarioCheck = Callable[[], Awaitable[tuple[bool, str, str]]]


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    suite: str
    description: str
    expected: str
    check: ScenarioCheck
    severity: Severity = Severity.MEDIUM
    timeout: float | None = None
    tags: tuple[str, ...] = ()
    requires_real_provider: bool = False
    related_modules: tuple[str, ...] = ()
    reproduction_steps: tuple[str, ...] = ()
    recommended_investigation: str = "Inspect the related modules and add a regression test."


@dataclass(frozen=True)
class ScenarioResult:
    scenario_id: str
    title: str
    suite: str
    started_at: datetime
    finished_at: datetime
    duration: float
    status: Status
    severity: Severity
    expected: str
    actual: str
    assertion_details: str = ""
    evidence: tuple[str, ...] = ()
    exception_type: str | None = None
    error_message: str | None = None
    related_modules: tuple[str, ...] = ()
    reproduction_steps: tuple[str, ...] = ()
    recommended_investigation: str = ""


@dataclass(frozen=True)
class RunReport:
    run_type: str
    started_at: datetime
    finished_at: datetime
    branch: str
    commit: str
    environment: str
    results: tuple[ScenarioResult, ...] = field(default_factory=tuple)

    def count(self, status: Status) -> int:
        return sum(result.status is status for result in self.results)
