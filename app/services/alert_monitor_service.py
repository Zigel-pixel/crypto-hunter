"""Background price-alert evaluation and delivery orchestration."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Protocol

from app.models.alert import Alert
from app.services.alerts_service import delete_alert, get_all_alerts, is_alert_triggered
from app.services.market_service import fetch_market_prices, format_price
from app.utils.config import ALERT_CHECK_INTERVAL_SECONDS

logger = logging.getLogger(__name__)


class AlertNotifier(Protocol):
    """Minimal notification contract used by the alert monitor."""

    async def send_message(self, chat_id: int, text: str) -> object:
        """Send a text notification to a chat."""


PriceFetcher = Callable[[], Awaitable[tuple[str | None, dict[str, float] | None]]]


async def monitor_alerts(
    notifier: AlertNotifier,
    check_interval_seconds: int = ALERT_CHECK_INTERVAL_SECONDS,
) -> None:
    """Continuously evaluate active alerts until the application stops."""
    while True:
        try:
            await process_alerts(notifier)
        except Exception:
            logger.exception("Unexpected alert-monitor error")
        await asyncio.sleep(check_interval_seconds)


async def process_alerts(
    notifier: AlertNotifier,
    price_fetcher: PriceFetcher = fetch_market_prices,
) -> None:
    """Fetch market prices once and deliver every alert whose condition is met."""
    _, prices = await price_fetcher()
    if not prices:
        logger.warning("Skipping alert evaluation because market prices are unavailable")
        return

    alerts = await get_all_alerts()
    for alert in alerts:
        price = prices.get(alert.coin)
        if price is None or not is_alert_triggered(alert, price):
            continue
        await _deliver_alert(notifier, alert, price)


async def _deliver_alert(
    notifier: AlertNotifier, alert: Alert, price: float
) -> None:
    try:
        await notifier.send_message(
            chat_id=alert.telegram_id,
            text=_build_alert_text(alert, price),
        )
    except Exception:
        logger.exception("Failed to deliver alert %s to %s", alert.id, alert.telegram_id)
        return

    deleted = await delete_alert(alert.id, alert.telegram_id)
    if not deleted:
        logger.warning("Delivered alert %s could not be removed", alert.id)


def _build_alert_text(alert: Alert, price: float) -> str:
    return "\n".join(
        [
            "🔔 Price Alert Triggered",
            "",
            f"{alert.coin}: {format_price(price)}",
            f"Target: {alert.condition} {format_price(alert.target_price)}",
        ]
    )
