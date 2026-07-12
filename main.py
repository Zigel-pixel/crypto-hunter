import asyncio
import sys
from contextlib import suppress
from pathlib import Path

from aiogram import Bot, Dispatcher

from app.database.database import init_db
from app.handlers.alerts import router as alerts_router
from app.handlers.assets import router as assets_router
from app.handlers.consultant import router as consultant_router
from app.handlers.favorites import router as favorites_router
from app.handlers.news import router as news_router
from app.handlers.portfolio import router as portfolio_router
from app.handlers.rates import router as rates_router
from app.handlers.settings import router as settings_router
from app.handlers.start import router as start_router
from app.handlers.wallet import router as wallet_router
from app.middlewares.live_cleanup import LiveCleanupMiddleware
from app.middlewares.user_session import UserSessionMiddleware
from app.services.alert_monitor_service import monitor_alerts
from app.services.live_market_service import live_task_manager
from app.utils.config import BOT_TOKEN
from app.utils.single_instance import InstanceAlreadyRunning, SingleInstanceLock

LOCK_FILE = Path(__file__).resolve().parent / ".crypto-hunter.lock"


async def main() -> None:
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.message.outer_middleware(UserSessionMiddleware())
    dp.callback_query.outer_middleware(UserSessionMiddleware())
    dp.message.outer_middleware(LiveCleanupMiddleware())
    dp.callback_query.outer_middleware(LiveCleanupMiddleware())

    dp.include_router(start_router)
    dp.include_router(rates_router)
    dp.include_router(assets_router)
    dp.include_router(favorites_router)
    dp.include_router(alerts_router)
    dp.include_router(news_router)
    dp.include_router(consultant_router)
    dp.include_router(portfolio_router)
    dp.include_router(settings_router)
    dp.include_router(wallet_router)

    await init_db()
    alert_monitor_task = asyncio.create_task(monitor_alerts(bot))
    try:
        await dp.start_polling(bot)
    finally:
        await live_task_manager.stop_all()
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
