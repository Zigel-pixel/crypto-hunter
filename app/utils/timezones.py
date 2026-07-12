from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def format_market_time(value: str, timezone_name: str | None) -> str:
    if not timezone_name or timezone_name == "UTC" or not value.endswith(" UTC"):
        return value
    try:
        parsed_time = datetime.strptime(value, "%H:%M:%S UTC").time()
        utc_value = datetime.combine(
            datetime.now(timezone.utc).date(), parsed_time, tzinfo=timezone.utc
        )
        local_value = utc_value.astimezone(ZoneInfo(timezone_name))
    except (ValueError, ZoneInfoNotFoundError):
        return value
    return f"{local_value.strftime('%H:%M:%S')} {timezone_name}"
