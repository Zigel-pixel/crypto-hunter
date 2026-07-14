from __future__ import annotations

import logging
import ssl
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import escape, unescape
from typing import Any
from xml.etree import ElementTree

import aiohttp
import certifi

from app.models.news import NewsItem

NEWS_RSS_URL = "https://www.coindesk.com/arc/outboundfeeds/rss/"
REQUEST_TIMEOUT_SECONDS = 15
NEWS_LIMIT = 7

logger = logging.getLogger(__name__)


async def get_news(limit: int = NEWS_LIMIT) -> list[NewsItem]:
    """Fetch the latest crypto headlines from a free public RSS feed."""
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(NEWS_RSS_URL, ssl=ssl_context) as response:
                response.raise_for_status()
                payload = await response.text()
    except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
        logger.warning("Crypto news request failed: %s", exc)
        return []

    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError as exc:
        logger.warning("Crypto news feed returned invalid XML: %s", exc)
        return []

    items: list[NewsItem] = []
    for element in root.findall("./channel/item"):
        title = _element_text(element.find("title"))
        url = _element_text(element.find("link"))
        if not title or not url or not url.startswith(("https://", "http://")):
            continue
        items.append(
            NewsItem(
                title=unescape(title).strip(),
                url=url.strip(),
                published_at=_parse_date(_element_text(element.find("pubDate"))),
            )
        )
        if len(items) >= max(1, limit):
            break
    return items


def build_news_text(items: list[NewsItem], language: str = "English") -> str:
    from app.utils.i18n import translate

    if not items:
        return translate("news.unavailable", language)
    lines = [translate("news.title", language), ""]
    for index, item in enumerate(items, start=1):
        published = _format_date(item.published_at)
        lines.append(
            f'{index}. <a href="{escape(item.url, quote=True)}">'
            f"{escape(item.title)}</a>"
        )
        if published:
            lines.append(f"   🕒 {published}")
        lines.append("")
    lines.append(translate("news.source", language))
    return "\n".join(lines)


def _element_text(element: Any) -> str:
    return element.text.strip() if element is not None and element.text else ""


def _parse_date(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _format_date(value: datetime | None) -> str:
    return "" if value is None else value.strftime("%d.%m %H:%M UTC")
