from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services.chart_service import TIMEFRAME_SECONDS, render_chart
from qa_bot.models import Scenario


async def chart_check():
    now = datetime.now(timezone.utc)
    png = render_chart([(now, 10), (now + timedelta(minutes=1), 11)], "QA")
    return png.startswith(b"\x89PNG") and len(png) > 100, f"Rendered PNG bytes: {len(png)}", "In-memory buffer only"


async def timeframe_check():
    expected = {"15m", "1h", "4h", "24h", "7d"}
    return set(TIMEFRAME_SECONDS) == expected, ", ".join(TIMEFRAME_SECONDS), "Timeframe registry"


def scenarios():
    return (
        Scenario("live.png", "Live chart PNG", "live", "Render a chart from deterministic points.", "Valid non-empty PNG", chart_check, related_modules=("app/services/chart_service.py",)),
        Scenario("live.timeframes", "Live timeframe mapping", "live", "Validate supported timeframe identifiers.", "15m, 1h, 4h, 24h, 7d", timeframe_check, related_modules=("app/services/chart_service.py",)),
    )
