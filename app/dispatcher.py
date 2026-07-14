from __future__ import annotations

from aiogram import Dispatcher

from app.handlers.alerts import router as alerts_router
from app.handlers.assets import router as assets_router
from app.handlers.consultant import question_router as consultant_question_router, router as consultant_router
from app.handlers.favorites import add_router as favorites_add_router, router as favorites_router
from app.handlers.news import router as news_router
from app.handlers.portfolio import router as portfolio_router
from app.handlers.rates import live_router, router as rates_router
from app.handlers.settings import router as settings_router
from app.handlers.start import router as start_router
from app.handlers.wallet import router as wallet_router
from app.middlewares.live_cleanup import LiveCleanupMiddleware
from app.middlewares.user_session import UserSessionMiddleware

PRODUCTION_ROUTERS = (
    start_router,
    consultant_question_router,
    favorites_add_router,
    live_router,
    rates_router,
    assets_router,
    favorites_router,
    alerts_router,
    news_router,
    consultant_router,
    portfolio_router,
    settings_router,
    wallet_router,
)


def build_dispatcher(*, with_middlewares: bool = True) -> Dispatcher:
    dispatcher = Dispatcher()
    if with_middlewares:
        dispatcher.message.outer_middleware(UserSessionMiddleware())
        dispatcher.callback_query.outer_middleware(UserSessionMiddleware())
        dispatcher.message.outer_middleware(LiveCleanupMiddleware())
        dispatcher.callback_query.outer_middleware(LiveCleanupMiddleware())
    for registered_router in PRODUCTION_ROUTERS:
        dispatcher.include_router(registered_router)
    return dispatcher
