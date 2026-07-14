from __future__ import annotations

import re
import os
from typing import Any

from qa_bot.security import redact

EVM_ADDRESS_RE = re.compile(r"\b0x[a-fA-F0-9]{40}\b")
TRON_ADDRESS_RE = re.compile(r"\bT[1-9A-HJ-NP-Za-km-z]{33}\b")
PHONE_RE = re.compile(r"(?<![A-Za-z0-9])\+?\d[\d ()-]{6,}\d(?![A-Za-z0-9])")
TECHNICAL_ERRORS = ("traceback", "keyerror", "typeerror", "sqlite3.", "environment variable")


def sanitize_text(value: Any) -> str:
    text = str(value)
    text = EVM_ADDRESS_RE.sub(lambda match: f"{match.group()[:6]}…{match.group()[-4:]}", text)
    text = TRON_ADDRESS_RE.sub(lambda match: f"{match.group()[:6]}…{match.group()[-4:]}", text)
    for name in ("E2E_TELEGRAM_PHONE", "E2E_TELEGRAM_API_HASH", "E2E_TELEGRAM_API_ID"):
        secret = os.getenv(name, "").strip()
        if secret:
            text = text.replace(secret, "[REDACTED PHONE]" if name.endswith("PHONE") else "[REDACTED]")

    def redact_phone(match: re.Match[str]) -> str:
        candidate = match.group()
        if re.search(r"\b\d{4}-\d{2}-\d{2}\b", candidate):
            return candidate
        digits = sum(character.isdigit() for character in candidate)
        formatted = candidate.startswith("+") or "(" in candidate or " " in candidate or candidate.count("-") >= 2
        return "[REDACTED PHONE]" if formatted and 8 <= digits <= 15 else candidate

    return PHONE_RE.sub(redact_phone, redact(text))[:1500]


def contains_raw_error(text: str) -> bool:
    normalized = text.casefold()
    return any(pattern in normalized for pattern in TECHNICAL_ERRORS)
