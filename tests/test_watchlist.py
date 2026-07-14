from __future__ import annotations

import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import AsyncMock, patch

import aiosqlite

from app.handlers.favorites import _detail_text, _watchlist_text, watchlist_add
from app.integrations.coingecko.market import CoinSnapshot
from app.services import favorites_service
from app.services.favorites_service import add_favorite, get_favorites, remove_favorite
from app.utils.assets import ASSET_REGISTRY


def snapshot(provider_id: str, symbol: str, change: float | None) -> CoinSnapshot:
    return CoinSnapshot(
        id=provider_id,
        name=symbol,
        symbol=symbol.lower(),
        price=100.0,
        change_24h=change,
        market_cap=None,
        volume_24h=None,
        market_rank=None,
        circulating_supply=None,
        ath=None,
        ath_change_percentage=None,
        updated_at="12:34:56 UTC",
    )


class WatchlistFormattingTests(unittest.TestCase):
    def test_empty_watchlist_has_useful_state(self) -> None:
        self.assertIn("no favorite coins", _watchlist_text([], {}))

    def test_positive_negative_and_missing_data(self) -> None:
        assets = list(ASSET_REGISTRY[:3])
        snapshots = {
            assets[0].provider_id: snapshot(assets[0].provider_id, assets[0].symbol, 2.5),
            assets[1].provider_id: snapshot(assets[1].provider_id, assets[1].symbol, -1.0),
        }
        with patch("app.handlers.favorites.market_data_is_stale", return_value=False):
            text = _watchlist_text(assets, snapshots)
        self.assertIn("🟢", text)
        self.assertIn("🔴", text)
        self.assertIn("unavailable", text)

    def test_detail_omits_missing_market_fields(self) -> None:
        text = _detail_text("Bitcoin", "BTC", snapshot("bitcoin", "BTC", 0.0))
        self.assertNotIn("Market cap", text)
        self.assertNotIn("24h volume", text)


class WatchlistPersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "test.db")
        self.original_db = favorites_service.DB_NAME
        favorites_service.DB_NAME = self.db_path
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE favorites (
                    telegram_id INTEGER, coin TEXT,
                    PRIMARY KEY (telegram_id, coin)
                )
                """
            )
            await db.commit()

    async def asyncTearDown(self) -> None:
        favorites_service.DB_NAME = self.original_db
        self.temp_dir.cleanup()

    async def test_duplicate_add_and_remove(self) -> None:
        self.assertTrue(await add_favorite(1, "BTC"))
        self.assertFalse(await add_favorite(1, "BTC"))
        self.assertEqual(await get_favorites(1), ["BTC"])
        self.assertTrue(await remove_favorite(1, "BTC"))
        self.assertFalse(await remove_favorite(1, "BTC"))


class WatchlistHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_add_handler_attaches_popular_full_name_buttons(self) -> None:
        message = SimpleNamespace(text="watchlist", caption=None)
        callback = SimpleNamespace(data="watchlist:add", message=message, from_user=SimpleNamespace(id=1), answer=AsyncMock())
        state = SimpleNamespace(set_state=AsyncMock())
        with patch("app.handlers.favorites.get_setting", AsyncMock(return_value="English")):
            message.answer = AsyncMock()
            await watchlist_add(callback, state)
        markup = message.answer.await_args.kwargs["reply_markup"]
        labels = [button.text for row in markup.inline_keyboard for button in row]
        callbacks = [button.callback_data for row in markup.inline_keyboard for button in row]
        self.assertIn("Bitcoin (BTC)", labels)
        self.assertIn("Ethereum (ETH)", labels)
        self.assertIn("Solana (SOL)", labels)
        self.assertIn("watchlist:add_asset:bitcoin", callbacks)
        state.set_state.assert_awaited_once()

    async def test_add_handler_localizes_ukrainian_prompt(self) -> None:
        message = SimpleNamespace(answer=AsyncMock())
        callback = SimpleNamespace(data="watchlist:add", message=message, from_user=SimpleNamespace(id=1), answer=AsyncMock())
        state = SimpleNamespace(set_state=AsyncMock())
        with patch("app.handlers.favorites.get_setting", AsyncMock(return_value="Ukrainian")):
            await watchlist_add(callback, state)
        self.assertIn("Оберіть популярний актив", message.answer.await_args.args[0])


if __name__ == "__main__":
    unittest.main()
