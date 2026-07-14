from __future__ import annotations

import re
from typing import Any

from qa_bot.security import redact

PHONE_RE = re.compile(r"(?<!\d)\+?\d[\d ()-]{7,}\d")
TECHNICAL_ERRORS = ("traceback", "keyerror", "typeerror", "sqlite3.", "environment variable")


def sanitize_text(value: Any) -> str:
    return PHONE_RE.sub("[REDACTED PHONE]", redact(value))[:1500]


def contains_raw_error(text: str) -> bool:
    normalized = text.casefold()
    return any(pattern in normalized for pattern in TECHNICAL_ERRORS)
