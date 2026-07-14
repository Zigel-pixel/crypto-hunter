from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


class QAConfigError(RuntimeError):
    pass


def _positive_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _boolean(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, "").strip().casefold()
    return default if not raw else raw in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class QAConfig:
    token: str
    admin_id: int
    reports_dir: Path
    scenario_timeout: int = 60
    max_parallel: int = 3
    real_provider_checks: bool = False
    github_issues_enabled: bool = False
    github_repository: str = "Zigel-pixel/crypto-hunter"
    deployment_state_path: Path = Path(".deployment/state.json")
    deployment_reports_dir: Path = Path(".deployment/reports")


def load_qa_config(*, load_env_file: bool = True) -> QAConfig:
    if load_env_file:
        load_dotenv()
    token = os.getenv("QA_BOT_TOKEN", "").strip()
    admin_raw = os.getenv("QA_ADMIN_TELEGRAM_ID", "").strip()
    if not token:
        raise QAConfigError("QA bot token is not configured")
    if not admin_raw:
        raise QAConfigError("QA administrator is not configured")
    try:
        admin_id = int(admin_raw)
    except ValueError as exc:
        raise QAConfigError("QA administrator identifier must be an integer") from exc
    if admin_id <= 0:
        raise QAConfigError("QA administrator identifier must be positive")
    return QAConfig(
        token=token,
        admin_id=admin_id,
        reports_dir=Path(os.getenv("QA_REPORTS_DIR", "qa/reports").strip() or "qa/reports"),
        scenario_timeout=_positive_int("QA_SCENARIO_TIMEOUT_SECONDS", 60),
        max_parallel=_positive_int("QA_MAX_PARALLEL_SCENARIOS", 3),
        real_provider_checks=_boolean("QA_REAL_PROVIDER_CHECKS"),
        github_issues_enabled=_boolean("QA_GITHUB_ISSUES_ENABLED"),
        github_repository=os.getenv("QA_GITHUB_REPOSITORY", "Zigel-pixel/crypto-hunter").strip() or "Zigel-pixel/crypto-hunter",
        deployment_state_path=Path(os.getenv("DEPLOYMENT_STATE_PATH", ".deployment/state.json").strip() or ".deployment/state.json"),
        deployment_reports_dir=Path(os.getenv("DEPLOYMENT_REPORTS_DIR", ".deployment/reports").strip() or ".deployment/reports"),
    )
