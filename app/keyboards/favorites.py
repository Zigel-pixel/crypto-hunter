from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.models.asset import AssetDefinition


def build_watchlist_keyboard(assets: list[AssetDefinition]) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text=f"{asset.symbol} · {asset.name}",
                callback_data=f"watchlist:open:{asset.provider_id}",
            )
        ]
        for asset in assets
    ]
    buttons.extend(
        [
            [InlineKeyboardButton(text="🔄 Refresh", callback_data="watchlist:refresh")],
            [InlineKeyboardButton(text="➕ Add coin", callback_data="watchlist:add")],
            [InlineKeyboardButton(text="➖ Remove coin", callback_data="watchlist:remove")],
            [InlineKeyboardButton(text="⬅ Back", callback_data="watchlist:back")],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_watchlist_search_results(
    assets: list[AssetDefinition],
) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text=f"{asset.symbol} · {asset.name}",
                callback_data=f"watchlist:add_asset:{asset.provider_id}",
            )
        ]
        for asset in assets
    ]
    buttons.append(
        [InlineKeyboardButton(text="⬅ Back", callback_data="watchlist:overview")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_popular_asset_keyboard(assets: list[AssetDefinition], language: str = "English") -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(text=f"{asset.name} ({asset.symbol})", callback_data=f"watchlist:add_asset:{asset.provider_id}")] for asset in assets]
    buttons.append([InlineKeyboardButton(text="❌ Скасувати" if language == "Ukrainian" else "❌ Cancel", callback_data="watchlist:overview")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_watchlist_remove_keyboard(
    assets: list[AssetDefinition],
) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text=f"➖ {asset.symbol} · {asset.name}",
                callback_data=f"watchlist:remove_asset:{asset.symbol}",
            )
        ]
        for asset in assets
    ]
    buttons.append(
        [InlineKeyboardButton(text="⬅ Back", callback_data="watchlist:overview")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_watchlist_detail_keyboard(
    provider_id: str, symbol: str
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Refresh",
                    callback_data=f"watchlist:detail_refresh:{provider_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🗑 Remove from Watchlist",
                    callback_data=f"watchlist:remove_asset:{symbol}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅ Back to Watchlist",
                    callback_data="watchlist:overview",
                )
            ],
        ]
    )
