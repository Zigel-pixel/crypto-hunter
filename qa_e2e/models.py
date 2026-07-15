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


@dataclass(frozen=True)
class ActiveReplyKeyboard:
    rows: tuple[tuple[str, ...], ...]
    source_message_id: int
    source_timestamp: datetime | None

    @property
    def labels(self) -> tuple[str, ...]:
        return tuple(label for row in self.rows for label in row)
