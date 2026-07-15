from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.models.asset import AssetDefinition
from app.utils.i18n import translate


def build_watchlist_keyboard(assets: list[AssetDefinition], language: str = "English") -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text=f"{asset.symbol} · {asset.name}",
                callback_data=f"watchlist:open:{asset.provider_id}",
            ),
            InlineKeyboardButton(
                text="📈 Графік" if language == "Ukrainian" else "📈 Chart",
                callback_data=f"watchlist:chart:{asset.provider_id}:1h",
            ),
        ]
        for asset in assets
    ]
    buttons.extend(
        [
            [InlineKeyboardButton(text=translate("common.refresh", language), callback_data="watchlist:refresh")],
            [InlineKeyboardButton(text="➕ Додати монету" if language == "Ukrainian" else "➕ Add coin", callback_data="watchlist:add")],
            [InlineKeyboardButton(text="➖ Видалити монету" if language == "Ukrainian" else "➖ Remove coin", callback_data="watchlist:remove")],
            [InlineKeyboardButton(text=translate("common.back", language), callback_data="watchlist:back")],
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
    provider_id: str, symbol: str, language: str = "English"
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📈 Графік" if language == "Ukrainian" else "📈 Chart",
                    callback_data=f"watchlist:chart:{provider_id}:1h",
                )
            ],
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


def build_watchlist_chart_keyboard(provider_id: str, timeframe: str, language: str = "English") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=("✓ " if timeframe == value else "") + value,
                              callback_data=f"watchlist:chart:{provider_id}:{value}")
         for value in ("15m", "1h", "4h", "24h", "7d")],
        [InlineKeyboardButton(text="⬅ До обраного" if language == "Ukrainian" else "⬅ Back to Watchlist",
                              callback_data="watchlist:overview")],
    ])
