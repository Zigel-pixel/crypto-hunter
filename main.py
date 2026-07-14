import asyncio
import sys
from contextlib import suppress
from pathlib import Path

from aiogram import Bot

from app.database.database import init_db
from app.dispatcher import build_dispatcher
from app.services.alert_monitor_service import monitor_alerts
from app.services.live_market_service import live_chart_manager
from app.utils.config import BOT_TOKEN
from app.utils.single_instance import InstanceAlreadyRunning, SingleInstanceLock

LOCK_FILE = Path(__file__).resolve().parent / ".crypto-hunter.lock"


async def main() -> None:
    bot = Bot(token=BOT_TOKEN)
    dp = build_dispatcher()

    await init_db()
    alert_monitor_task = asyncio.create_task(monitor_alerts(bot))
    try:
        await dp.start_polling(bot)
    finally:
        await live_chart_manager.stop_all()
        alert_monitor_task.cancel()
        with suppress(asyncio.CancelledError):
            await alert_monitor_task


def run() -> int:
    try:
        with SingleInstanceLock(LOCK_FILE):
            asyncio.run(main())
    except InstanceAlreadyRunning as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
