from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class Status(StrEnum):
    PASSED = "passed"
    PASSED_WITH_RETRY = "passed_with_retry"
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


class FailureCategory(StrEnum):
    PRODUCT_ASSERTION_FAILED = "product_assertion_failed"
    PRODUCT_RESPONSE_TIMEOUT = "product_response_timeout"
    INFRASTRUCTURE_NOT_READY = "infrastructure_not_ready"
    TELEGRAM_TRANSIENT = "telegram_transient"
    TEST_STATE_INVALID = "test_state_invalid"
    CONFIGURATION_ERROR = "configuration_error"
    EXTERNAL_PROVIDER_ERROR = "external_provider_error"
    DEPLOYMENT_HEALTH_FAILED = "deployment_health_failed"
    TEST_IMPLEMENTATION_ERROR = "test_implementation_error"


RETRYABLE_FAILURES = frozenset({
    FailureCategory.TELEGRAM_TRANSIENT,
    FailureCategory.INFRASTRUCTURE_NOT_READY,
})


@dataclass(frozen=True)
class NamedAssertion:
    name: str
    passed: bool
    detail: str = ""


@dataclass(frozen=True)
class CheckResult:
    passed: bool
    actual: str
    details: str = ""
    failure_category: FailureCategory | None = None
    failed_predicate: str | None = None
    assertions: tuple[NamedAssertion, ...] = ()


ScenarioCheck = Callable[[], Awaitable[tuple[bool, str, str] | CheckResult]]


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
    retry_categories: tuple[FailureCategory, ...] = ()
    max_retries: int = 0


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
    failure_category: FailureCategory | None = None
    failed_predicate: str | None = None
    assertions: tuple[NamedAssertion, ...] = ()
    retry_count: int = 0
    retry_details: tuple[str, ...] = ()


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
