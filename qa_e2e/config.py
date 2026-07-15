from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SESSION_ROOT = (PROJECT_ROOT / "qa/e2e_sessions").resolve()
REPORT_ROOT = (PROJECT_ROOT / "qa/e2e_reports").resolve()
ARTIFACT_ROOT = (PROJECT_ROOT / "qa/e2e_artifacts").resolve()
USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{4,31}$")


class E2EConfigError(RuntimeError):
    pass


def _bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name, "").strip().casefold()
    if not value:
        return default
    if value not in {"true", "false", "1", "0", "yes", "no", "on", "off"}:
        raise E2EConfigError(f"Invalid boolean configuration: {name}")
    return value in {"true", "1", "yes", "on"}


def _int(name: str, default: int | None = None) -> int:
    value = os.getenv(name, "").strip()
    if not value and default is not None:
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise E2EConfigError(f"Invalid integer configuration: {name}") from exc
    if parsed <= 0:
        raise E2EConfigError(f"Configuration must be positive: {name}")
    return parsed


def _safe_path(name: str, default: str, root: Path) -> Path:
    raw = os.getenv(name, default).strip() or default
    candidate = Path(raw)
    if candidate.is_absolute():
        raise E2EConfigError(f"Absolute paths are not allowed: {name}")
    resolved = (PROJECT_ROOT / candidate).resolve()
    if resolved != root and root not in resolved.parents:
        raise E2EConfigError(f"Path escapes its allowed E2E directory: {name}")
    return resolved


@dataclass(frozen=True)
class E2EConfig:
    enabled: bool
    api_id: int
    api_hash: str
    phone: str
    target_username: str
    session_path: Path
    reports_dir: Path
    artifacts_dir: Path
    default_timeout: int = 20
    long_timeout: int = 90
    settle_seconds: int = 2
    max_scenario_seconds: int = 180
    allow_destructive: bool = False
    test_language: str = "uk"
    live_wait_seconds: int = 50
    readiness_timeout: int = 30
    product_response_sla: int = 20


def load_e2e_config(*, load_env_file: bool = True, require_enabled: bool = True) -> E2EConfig:
    if load_env_file:
        load_dotenv()
    enabled = _bool("E2E_ENABLED")
    if require_enabled and not enabled:
        raise E2EConfigError("Telegram E2E is disabled")
    api_hash = os.getenv("E2E_TELEGRAM_API_HASH", "").strip()
    phone = os.getenv("E2E_TELEGRAM_PHONE", "").strip()
    username = os.getenv("E2E_TARGET_BOT_USERNAME", "").strip().removeprefix("@")
    if not api_hash: raise E2EConfigError("Telegram API hash is not configured")
    if not phone: raise E2EConfigError("Telegram phone is not configured")
    if not USERNAME_RE.fullmatch(username): raise E2EConfigError("Target bot username is invalid")
    language = os.getenv("E2E_TEST_LANGUAGE", "uk").strip().casefold() or "uk"
    if language not in {"en", "uk"}: raise E2EConfigError("E2E test language must be en or uk")
    return E2EConfig(
        enabled, _int("E2E_TELEGRAM_API_ID"), api_hash, phone, username,
        _safe_path("E2E_SESSION_PATH", "qa/e2e_sessions/crypto-hunter-e2e", SESSION_ROOT),
        _safe_path("E2E_REPORTS_DIR", "qa/e2e_reports", REPORT_ROOT),
        _safe_path("E2E_ARTIFACTS_DIR", "qa/e2e_artifacts", ARTIFACT_ROOT),
        _int("E2E_DEFAULT_TIMEOUT_SECONDS", 20), _int("E2E_LONG_TIMEOUT_SECONDS", 90),
        _int("E2E_MESSAGE_SETTLE_SECONDS", 2), _int("E2E_MAX_SCENARIO_SECONDS", 180),
        _bool("E2E_ALLOW_DESTRUCTIVE_SCENARIOS"), language, _int("E2E_LIVE_WAIT_SECONDS", 50),
        _int("E2E_READINESS_TIMEOUT_SECONDS", 30), _int("E2E_PRODUCT_RESPONSE_SLA_SECONDS", 20),
    )
