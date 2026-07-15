from __future__ import annotations

import logging

import aiosqlite
from aiogram import F, Router, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.handlers.common import user_main_keyboard
from app.handlers.message_updates import safe_update_message, safe_update_photo
from app.keyboards.favorites import (
    build_watchlist_detail_keyboard,
    build_watchlist_keyboard,
    build_watchlist_remove_keyboard,
    build_watchlist_search_results,
    build_popular_asset_keyboard,
    build_watchlist_chart_keyboard,
)
from app.services.chart_service import build_timeframe_chart
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
from app.services.settings_service import get_setting, resolve_user_language
from aiogram.types import BufferedInputFile
from app.utils.timezones import format_market_time

router = Router(name="favorites")
add_router = Router(name="favorites_add")
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
    language = await resolve_user_language(message.from_user.id)
    results = search_assets(message.text or "")
    if not results:
        await message.answer("Не знайдено монету за цією назвою або тикером." if language == "Ukrainian" else "No supported coin matched that name or ticker. Try again.")
        return
    await state.clear()
    await message.answer(
        "Оберіть точну монету:" if language == "Ukrainian" else "Select the exact coin to add:",
        reply_markup=build_watchlist_search_results(results),
    )


@add_router.callback_query(F.data == "watchlist:add")
async def watchlist_add(callback: types.CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        await callback.answer()
        return
    await state.set_state(WatchlistStates.searching)
    language = await resolve_user_language(callback.from_user.id)
    popular_symbols = {"BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "ADA", "TRX"}
    popular = [asset for asset in list_supported_assets() if asset.symbol in popular_symbols]
    text = "Оберіть популярний актив або введіть назву/тикер:" if language == "Ukrainian" else "Choose a popular asset or type any name/ticker:"
    await callback.message.answer(text, reply_markup=build_popular_asset_keyboard(popular, language))
    await callback.answer()


@router.callback_query(lambda callback: callback.data and callback.data.startswith("watchlist:") and callback.data != "watchlist:add")
async def watchlist_callback(
    callback: types.CallbackQuery, state: FSMContext
) -> None:
    if callback.message is None:
        await callback.answer()
        return
    data = callback.data or ""
    language = await resolve_user_language(callback.from_user.id)
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

        if data.startswith("watchlist:chart:"):
            _, _, provider_id, timeframe = data.split(":", 3)
            await _show_watchlist_chart(callback.message, provider_id, timeframe, language)
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
        language = await resolve_user_language(message.from_user.id)
    except aiosqlite.Error as exc:
        logger.exception("Could not load Watchlist: %s", exc)
        await message.answer("Watchlist is temporarily unavailable.")
        return
    await message.answer(
        _watchlist_text(assets, snapshots or {}, timezone_name=timezone_name, language=language),
        reply_markup=build_watchlist_keyboard(assets, language),
    )


async def _update_watchlist(
    message: types.Message, telegram_id: int, *, force_refresh: bool = False
) -> None:
    assets = await get_favorite_assets(telegram_id)
    _, snapshots = await fetch_market_snapshots(force_refresh=force_refresh)
    timezone_name = await get_setting(telegram_id, "timezone")
    language = await resolve_user_language(telegram_id)
    await safe_update_message(
        message,
        _watchlist_text(assets, snapshots or {}, timezone_name=timezone_name, language=language),
        build_watchlist_keyboard(assets, language),
    )


def _watchlist_text(
    assets: list[AssetDefinition],
    snapshots: dict[str, CoinSnapshot],
    *,
    timezone_name: str | None = None,
    language: str = "English",
) -> str:
    if not assets:
        return "⭐ Обране\n\nУ вас ще немає обраних монет." if language == "Ukrainian" else "⭐ Watchlist\n\nYou have no favorite coins yet."
    lines = ["⭐ Обране" if language == "Ukrainian" else "⭐ Watchlist", ""]
    for asset in assets:
        snapshot = snapshots.get(asset.provider_id)
        if snapshot is None:
            lines.append(f"⚪ {asset.symbol} — {'недоступно' if language == 'Ukrainian' else 'unavailable'}")
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
                (f"⚠️ Показано кешовані дані від {updated}" if language == "Ukrainian" else f"⚠️ Showing cached data from {updated}")
                if market_data_is_stale()
                else (f"🕒 Оновлено: {updated}" if language == "Ukrainian" else f"🕒 Updated: {updated}")
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
            language=await resolve_user_language(telegram_id),
        ),
        build_watchlist_detail_keyboard(asset.provider_id, asset.symbol, await resolve_user_language(telegram_id)),
    )


async def _show_watchlist_chart(message: types.Message, provider_id: str, timeframe: str, language: str) -> None:
    asset = get_asset(provider_id)
    if asset is None:
        await safe_update_message(message, "Невідомий актив." if language == "Ukrainian" else "Unknown asset.", None)
        return
    result = await build_timeframe_chart(provider_id, asset.symbol, timeframe)
    keyboard = build_watchlist_chart_keyboard(provider_id, timeframe, language)
    if result is None:
        text = "Для цього періоду недостатньо даних графіка." if language == "Ukrainian" else "Not enough chart history is available for this timeframe."
        await safe_update_message(message, text, keyboard)
        return
    chart, points = result
    first, latest = points[0][1], points[-1][1]
    percent = ((latest - first) / first * 100) if first else 0
    caption = f"📈 {asset.name} ({asset.symbol}) · {timeframe}\n\n${latest:,.4f}\n{percent:+.2f}%"
    await safe_update_photo(message, BufferedInputFile(chart, filename=f"watchlist-{asset.symbol}-{timeframe}.png"), caption, keyboard)


def _detail_text(
    name: str,
    symbol: str,
    snapshot: CoinSnapshot | None,
    *,
    timezone_name: str | None = None,
    stale: bool = False,
    language: str = "English",
) -> str:
    if snapshot is None:
        return f"{name} ({symbol})\n\n" + ("Ринкові дані зараз недоступні." if language == "Ukrainian" else "Current market data is unavailable.")
    fields = [
        f"{name} ({symbol})",
        "",
        f"{'Ціна' if language == 'Ukrainian' else 'Price'}: {format_price(snapshot.price)}",
        f"24h: {format_percent(snapshot.change_24h)}",
    ]
    optional = [
        ("Максимум 24г" if language == "Ukrainian" else "24h high", snapshot.high_24h, format_price),
        ("Мінімум 24г" if language == "Ukrainian" else "24h low", snapshot.low_24h, format_price),
        ("Капіталізація" if language == "Ukrainian" else "Market cap", snapshot.market_cap, format_compact_currency),
        ("Обсяг 24г" if language == "Ukrainian" else "24h volume", snapshot.volume_24h, format_compact_currency),
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
                ("⚠️ Показано кешовані дані від " if language == "Ukrainian" else "⚠️ Showing cached data from ") +
                f"{format_market_time(snapshot.updated_at, timezone_name)}"
                if stale
                else ("🕒 Оновлено: " if language == "Ukrainian" else "🕒 Updated: ") +
                f"{format_market_time(snapshot.updated_at, timezone_name)}"
            ),
            "Source: CoinGecko",
        ]
    )
    return "\n".join(fields)
