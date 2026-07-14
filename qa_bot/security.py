from __future__ import annotations

import re
from typing import Any

SECRET_PATTERNS = (
    re.compile(r"(?i)(token|api[_ -]?key|secret|password)\s*[:=]\s*\S+"),
    re.compile(r"\b\d{8,}:[A-Za-z0-9_-]{20,}\b"),
)


def is_authorized(user_id: int | None, admin_id: int) -> bool:
    return user_id is not None and user_id == admin_id


def redact(value: Any) -> str:
    text = str(value)
    for pattern in SECRET_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text[:2000]


def safe_exception(exc: BaseException) -> tuple[str, str]:
    return type(exc).__name__, redact(str(exc) or "Scenario failed without details")
