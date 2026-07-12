from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from app.models.asset import AssetDefinition

BROWSE_ASSETS_BUTTON = "📋 Browse Assets"
SEARCH_ASSETS_BUTTON = "🔎 Search Asset"
BACK_BUTTON = "⬅ Back"


def build_assets_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BROWSE_ASSETS_BUTTON)],
            [KeyboardButton(text=SEARCH_ASSETS_BUTTON)],
            [KeyboardButton(text=BACK_BUTTON)],
        ],
        resize_keyboard=True,
    )


def build_asset_list_keyboard(
    assets: list[AssetDefinition] | tuple[AssetDefinition, ...],
) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=asset.label, callback_data=f"assets:open:{asset.provider_id}")]
        for asset in assets
    ]
    buttons.append([InlineKeyboardButton(text="⬅ Back", callback_data="assets:back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_asset_page_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Refresh", callback_data="assets:refresh")],
            [InlineKeyboardButton(text="⬅ Back", callback_data="assets:list")],
        ]
    )
