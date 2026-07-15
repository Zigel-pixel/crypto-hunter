from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class NewsItem:
    title: str
    url: str
    published_at: datetime | None
    summary: str | None = None
    original_title: str | None = None
    translation_fallback: bool = False

