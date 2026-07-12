import asyncio

from aiogram import Bot, Dispatcher

from app.database.database import init_db
from app.handlers.alerts import router as alerts_router
from app.handlers.favorites import router as favorites_router
from app.handlers.news import router as news_router
from app.handlers.portfolio import router as portfolio_router
from app.handlers.rates import router as rates_router
from app.handlers.settings import router as settings_router
from app.handlers.start import router as start_router
from app.handlers.wallet import router as wallet_router
from app.utils.config import BOT_TOKEN


async def main() -> None:
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    dp.include_router(start_router)
    dp.include_router(rates_router)
    dp.include_router(favorites_router)
    dp.include_router(alerts_router)
    dp.include_router(news_router)
    dp.include_router(portfolio_router)
    dp.include_router(settings_router)
    dp.include_router(wallet_router)

    await init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
