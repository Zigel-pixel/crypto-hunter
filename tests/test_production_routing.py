from __future__ import annotations

import unittest
from pathlib import Path

from app.dispatcher import PRODUCTION_ROUTERS, build_dispatcher
from app.handlers.consultant import answer_question, question_router
from app.handlers.favorites import add_router, watchlist_add
from app.handlers.rates import handle_live_callback, live_router
from app.keyboards.favorites import build_popular_asset_keyboard
from app.handlers.rates import build_live_keyboard
from app.services.asset_service import list_supported_assets


def callbacks(router, observer: str) -> tuple[object, ...]:
    return tuple(item.callback for item in router.observers[observer].handlers)


class ProductionRoutingAuditTests(unittest.TestCase):
    def test_application_dispatcher_uses_audited_router_graph(self) -> None:
        dispatcher = build_dispatcher(with_middlewares=False)
        self.assertEqual(tuple(dispatcher.sub_routers), PRODUCTION_ROUTERS)

    def test_dedicated_routes_are_registered_before_general_feature_routers(self) -> None:
        names = tuple(router.name for router in PRODUCTION_ROUTERS)
        self.assertLess(names.index(question_router.name), names.index("consultant"))
        self.assertLess(names.index(add_router.name), names.index("favorites"))
        self.assertLess(names.index(live_router.name), names.index("rates"))

    def test_each_verified_action_has_exactly_one_production_owner(self) -> None:
        message_callbacks = [callback for router in PRODUCTION_ROUTERS for callback in callbacks(router, "message")]
        callback_callbacks = [callback for router in PRODUCTION_ROUTERS for callback in callbacks(router, "callback_query")]
        self.assertEqual(message_callbacks.count(answer_question), 1)
        self.assertEqual(callback_callbacks.count(watchlist_add), 1)
        self.assertEqual(callback_callbacks.count(handle_live_callback), 1)
        self.assertIn(answer_question, callbacks(question_router, "message"))
        self.assertIn(watchlist_add, callbacks(add_router, "callback_query"))
        self.assertIn(handle_live_callback, callbacks(live_router, "callback_query"))

    def test_callback_data_stays_within_telegram_limit(self) -> None:
        popular = build_popular_asset_keyboard(list_supported_assets(), "English")
        live = build_live_keyboard()
        values = [button.callback_data for markup in (popular, live) for row in markup.inline_keyboard for button in row if button.callback_data]
        self.assertTrue(values)
        self.assertTrue(all(len(value.encode("utf-8")) <= 64 for value in values))

    def test_legacy_live_route_is_not_imported_by_production(self) -> None:
        production = "\n".join(Path(path).read_text(encoding="utf-8") for path in (
            "main.py", "app/dispatcher.py", "app/handlers/rates.py", "app/services/live_market_service.py", "app/middlewares/live_cleanup.py"
        ))
        self.assertNotIn("live_task_manager", production)
        self.assertNotIn("BinanceLiveProvider", production)
        self.assertNotIn("Live Crypto / USDT", production)
        self.assertNotIn("Send a ticker or name", production)


if __name__ == "__main__":
    unittest.main()
