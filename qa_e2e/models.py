from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class MessageEvidence:
    message_id: int
    timestamp: datetime | None
    text: str
    media_type: str | None
    inline_buttons: tuple[str, ...]
    reply_buttons: tuple[str, ...]
    response_seconds: float
    edited: bool = False


@dataclass(frozen=True)
class ActionResult:
    action: str
    baseline_id: int
    messages: tuple[MessageEvidence, ...]
    first_response_seconds: float | None
    total_seconds: float
