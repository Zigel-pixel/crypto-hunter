from __future__ import annotations

from aiogram import Router, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.handlers.common import user_main_keyboard
from app.handlers.message_updates import safe_update_message
from app.keyboards.assets import (
    BACK_BUTTON,
    BROWSE_ASSETS_BUTTON,
    SEARCH_ASSETS_BUTTON,
    build_asset_list_keyboard,
    build_asset_page_keyboard,
    build_assets_keyboard,
)
from app.services.asset_service import (
    get_asset,
    get_asset_snapshot,
    list_supported_assets,
    search_assets,
)
from app.services.market_service import (
    CoinSnapshot,
    format_compact_currency,
    format_percent,
    format_price,
    market_refresh_in_progress,
    market_data_is_stale,
)

ASSETS_MENU_BUTTON = "🔎 Assets"
router = Router()


class AssetStates(StatesGroup):
    searching = State()


@router.message(Command("assets"))
@router.message(lambda message: message.text == ASSETS_MENU_BUTTON)
async def assets_entry(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("🔎 Assets", reply_markup=build_assets_keyboard())


@router.message(lambda message: message.text == BROWSE_ASSETS_BUTTON)
async def browse_assets(message: types.Message) -> None:
    await message.answer(
        "Supported assets:",
        reply_markup=build_asset_list_keyboard(list_supported_assets()),
    )


@router.message(lambda message: message.text == SEARCH_ASSETS_BUTTON)
async def search_asset_entry(message: types.Message, state: FSMContext) -> None:
    await state.set_state(AssetStates.searching)
    await message.answer("Send an asset name or ticker, for example BTC or Cardano:")


@router.message(lambda message: message.text != BACK_BUTTON, AssetStates.searching)
async def search_asset(message: types.Message, state: FSMContext) -> None:
    results = search_assets(message.text or "")
    if not results:
        await message.answer(
            "No supported assets matched that search. Try another name or ticker."
        )
        return
    await state.clear()
    await message.answer("Search results:", reply_markup=build_asset_list_keyboard(results))


@router.callback_query(
    lambda callback: callback.data and callback.data.startswith("assets:")
)
async def assets_callback(callback: types.CallbackQuery, state: FSMContext) -> None:
    data = callback.data or ""
    if callback.message is None:
        await callback.answer()
        return
    if data == "assets:back":
        await safe_update_message(callback.message, "↩ Assets menu", None)
        await callback.answer()
        return
    if data == "assets:list":
        await safe_update_message(
            callback.message,
            "Supported assets:",
            build_asset_list_keyboard(list_supported_assets()),
        )
        await callback.answer()
        return
    if data == "assets:refresh":
        if market_refresh_in_progress():
            await callback.answer("Updating…")
            return
        stored = await state.get_data()
        provider_id = stored.get("asset_provider_id")
        force_refresh = True
    else:
        provider_id = (
            data.split(":", 2)[2] if data.startswith("assets:open:") else None
        )
        force_refresh = False
    asset = get_asset(provider_id) if isinstance(provider_id, str) else None
    if asset is None:
        await callback.answer("Asset is unavailable.", show_alert=True)
        return
    await state.update_data(asset_provider_id=asset.provider_id)
    snapshot = await get_asset_snapshot(
        asset.provider_id, force_refresh=force_refresh
    )
    await safe_update_message(
        callback.message,
        _asset_page_text(asset.name, asset.symbol, snapshot),
        build_asset_page_keyboard(),
    )
    await callback.answer()


def _asset_page_text(name: str, symbol: str, snapshot: CoinSnapshot | None) -> str:
    if snapshot is None:
        return f"{name} ({symbol})\n\nCurrent market data is unavailable.\nSource: CoinGecko"
    return "\n".join(
        [
            f"{name} ({symbol})",
            "",
            "Price",
            format_price(snapshot.price),
            "",
            "24h change",
            format_percent(snapshot.change_24h),
            "",
            "24h high / low",
            f"{format_price(snapshot.high_24h)} / {format_price(snapshot.low_24h)}",
            "",
            "Market cap",
            format_compact_currency(snapshot.market_cap),
            "",
            "24h volume",
            format_compact_currency(snapshot.volume_24h),
            "",
            "Source: CoinGecko",
            (
                f"⚠️ Showing cached data from {snapshot.updated_at}"
                if market_data_is_stale()
                else f"🕒 Updated: {snapshot.updated_at}"
            ),
        ]
    )


@router.message(lambda message: message.text == BACK_BUTTON, StateFilter(None))
@router.message(lambda message: message.text == BACK_BUTTON, AssetStates.searching)
async def assets_back(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "↩ Main menu",
        reply_markup=await user_main_keyboard(message.from_user.id),
    )
