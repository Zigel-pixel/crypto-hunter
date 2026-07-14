from __future__ import annotations

import logging

import aiosqlite
from aiogram import Router, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.handlers.common import user_main_keyboard
from app.handlers.message_updates import safe_update_message
from app.keyboards.favorites import (
    build_watchlist_detail_keyboard,
    build_watchlist_keyboard,
    build_watchlist_remove_keyboard,
    build_watchlist_search_results,
    build_popular_asset_keyboard,
)
from app.services.asset_service import get_asset, list_supported_assets, search_assets
from app.models.asset import AssetDefinition
from app.services.favorites_service import (
    add_favorite,
    get_favorite_assets,
    remove_favorite,
)
from app.services.market_service import (
    CoinSnapshot,
    fetch_market_snapshots,
    format_compact_currency,
    format_percent,
    format_price,
    market_data_is_stale,
    market_refresh_in_progress,
)
from app.services.settings_service import get_setting
from app.utils.timezones import format_market_time

router = Router()
logger = logging.getLogger(__name__)
WATCHLIST_LABELS = {"⭐ Favorites", "⭐ Watchlist", "⭐ Обране", "⭐ Избранное", "⭐ 收藏"}


class WatchlistStates(StatesGroup):
    searching = State()


@router.message(lambda message: message.text in WATCHLIST_LABELS)
async def watchlist_entry(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await _send_watchlist(message)


@router.message(WatchlistStates.searching)
async def watchlist_search(message: types.Message, state: FSMContext) -> None:
    language = await get_setting(message.from_user.id, "language") or "English"
    results = search_assets(message.text or "")
    if not results:
        await message.answer("Не знайдено монету за цією назвою або тикером." if language == "Ukrainian" else "No supported coin matched that name or ticker. Try again.")
        return
    await state.clear()
    await message.answer(
        "Оберіть точну монету:" if language == "Ukrainian" else "Select the exact coin to add:",
        reply_markup=build_watchlist_search_results(results),
    )


@router.callback_query(
    lambda callback: callback.data and callback.data.startswith("watchlist:")
)
async def watchlist_callback(
    callback: types.CallbackQuery, state: FSMContext
) -> None:
    if callback.message is None:
        await callback.answer()
        return
    data = callback.data or ""
    try:
        if data in {"watchlist:overview", "watchlist:refresh"}:
            if data.endswith("refresh") and market_refresh_in_progress():
                await callback.answer("Updating…")
                return
            if data.endswith("refresh"):
                await callback.answer("Updating…")
            await _update_watchlist(
                callback.message,
                callback.from_user.id,
                force_refresh=data.endswith("refresh"),
            )
            if not data.endswith("refresh"):
                await callback.answer()
            return

        if data == "watchlist:add":
            await state.set_state(WatchlistStates.searching)
            language = await get_setting(callback.from_user.id, "language") or "English"
            popular_symbols = {"BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "ADA", "TRX"}
            popular = [asset for asset in list_supported_assets() if asset.symbol in popular_symbols]
            text = "Оберіть популярний актив або введіть назву/тикер:" if language == "Ukrainian" else "Choose a popular asset or type any name/ticker:"
            await safe_update_message(callback.message, text, build_popular_asset_keyboard(popular, language))
            await callback.answer()
            return

        if data == "watchlist:remove":
            assets = await get_favorite_assets(callback.from_user.id)
            await safe_update_message(
                callback.message,
                "Select a coin to remove:" if assets else "Your Watchlist is empty.",
                build_watchlist_remove_keyboard(assets),
            )
            await callback.answer()
            return

        if data == "watchlist:back":
            await safe_update_message(callback.message, "↩ Watchlist closed", None)
            await callback.message.answer(
                "↩ Main menu",
                reply_markup=await user_main_keyboard(callback.from_user.id),
            )
            await callback.answer()
            return

        if data.startswith("watchlist:add_asset:"):
            asset = get_asset(data.split(":", 2)[2])
            if asset is None:
                await callback.answer("Unknown coin.", show_alert=True)
                return
            added = await add_favorite(callback.from_user.id, asset.symbol)
            await _update_watchlist(callback.message, callback.from_user.id)
            await callback.answer(
                f"{asset.symbol} added" if added else f"{asset.symbol} is already saved"
            )
            return

        if data.startswith("watchlist:remove_asset:"):
            symbol = data.split(":", 2)[2]
            removed = await remove_favorite(callback.from_user.id, symbol)
            await _update_watchlist(callback.message, callback.from_user.id)
            await callback.answer(f"{symbol} removed" if removed else "Coin was not saved")
            return

        if data.startswith(("watchlist:open:", "watchlist:detail_refresh:")):
            refresh = data.startswith("watchlist:detail_refresh:")
            if refresh and market_refresh_in_progress():
                await callback.answer("Updating…")
                return
            if refresh:
                await callback.answer("Updating…")
            provider_id = data.split(":", 2)[2]
            await _show_detail(
                callback.message,
                callback.from_user.id,
                provider_id,
                force_refresh=refresh,
            )
            if not refresh:
                await callback.answer()
            return

        await callback.answer("This Watchlist action is no longer available.")
    except aiosqlite.Error as exc:
        logger.exception("Watchlist database operation failed: %s", exc)
        try:
            await callback.answer("Watchlist is temporarily unavailable.", show_alert=True)
        except TelegramBadRequest as callback_exc:
            logger.debug("Could not answer expired Watchlist callback: %s", callback_exc)
        await callback.message.answer("Watchlist is temporarily unavailable.")


async def _send_watchlist(message: types.Message) -> None:
    try:
        assets = await get_favorite_assets(message.from_user.id)
        _, snapshots = await fetch_market_snapshots()
        timezone_name = await get_setting(message.from_user.id, "timezone")
    except aiosqlite.Error as exc:
        logger.exception("Could not load Watchlist: %s", exc)
        await message.answer("Watchlist is temporarily unavailable.")
        return
    await message.answer(
        _watchlist_text(assets, snapshots or {}, timezone_name=timezone_name),
        reply_markup=build_watchlist_keyboard(assets),
    )


async def _update_watchlist(
    message: types.Message, telegram_id: int, *, force_refresh: bool = False
) -> None:
    assets = await get_favorite_assets(telegram_id)
    _, snapshots = await fetch_market_snapshots(force_refresh=force_refresh)
    timezone_name = await get_setting(telegram_id, "timezone")
    await safe_update_message(
        message,
        _watchlist_text(assets, snapshots or {}, timezone_name=timezone_name),
        build_watchlist_keyboard(assets),
    )


def _watchlist_text(
    assets: list[AssetDefinition],
    snapshots: dict[str, CoinSnapshot],
    *,
    timezone_name: str | None = None,
) -> str:
    if not assets:
        return "⭐ Watchlist\n\nYou have no favorite coins yet."
    lines = ["⭐ Watchlist", ""]
    for asset in assets:
        snapshot = snapshots.get(asset.provider_id)
        if snapshot is None:
            lines.append(f"⚪ {asset.symbol} — unavailable")
            continue
        change = snapshot.change_24h
        marker = (
            "🟢"
            if change is not None and change > 0
            else "🔴"
            if change is not None and change < 0
            else "⚪"
        )
        lines.append(
            f"{marker} {asset.symbol} · {asset.name} — "
            f"{format_price(snapshot.price)} | {format_percent(change)}"
        )
    updated = next((item.updated_at for item in snapshots.values()), "N/A")
    updated = format_market_time(updated, timezone_name)
    lines.extend(
        [
            "",
            (
                f"⚠️ Showing cached data from {updated}"
                if market_data_is_stale()
                else f"🕒 Updated: {updated}"
            ),
            "Source: CoinGecko",
        ]
    )
    return "\n".join(lines)


async def _show_detail(
    message: types.Message,
    telegram_id: int,
    provider_id: str,
    *,
    force_refresh: bool,
) -> None:
    asset = get_asset(provider_id)
    if asset is None:
        await safe_update_message(message, "Unknown coin.", build_watchlist_keyboard([]))
        return
    _, snapshots = await fetch_market_snapshots(force_refresh=force_refresh)
    snapshot = snapshots.get(provider_id) if snapshots else None
    timezone_name = await get_setting(telegram_id, "timezone")
    await safe_update_message(
        message,
        _detail_text(
            asset.name,
            asset.symbol,
            snapshot,
            timezone_name=timezone_name,
            stale=market_data_is_stale(),
        ),
        build_watchlist_detail_keyboard(asset.provider_id, asset.symbol),
    )


def _detail_text(
    name: str,
    symbol: str,
    snapshot: CoinSnapshot | None,
    *,
    timezone_name: str | None = None,
    stale: bool = False,
) -> str:
    if snapshot is None:
        return f"{name} ({symbol})\n\nCurrent market data is unavailable."
    fields = [
        f"{name} ({symbol})",
        "",
        f"Price: {format_price(snapshot.price)}",
        f"24h: {format_percent(snapshot.change_24h)}",
    ]
    optional = [
        ("24h high", snapshot.high_24h, format_price),
        ("24h low", snapshot.low_24h, format_price),
        ("Market cap", snapshot.market_cap, format_compact_currency),
        ("24h volume", snapshot.volume_24h, format_compact_currency),
    ]
    fields.extend(
        f"{label}: {formatter(value)}"
        for label, value, formatter in optional
        if value is not None
    )
    fields.extend(
        [
            "",
            (
                "⚠️ Showing cached data from "
                f"{format_market_time(snapshot.updated_at, timezone_name)}"
                if stale
                else "🕒 Updated: "
                f"{format_market_time(snapshot.updated_at, timezone_name)}"
            ),
            "Source: CoinGecko",
        ]
    )
    return "\n".join(fields)
