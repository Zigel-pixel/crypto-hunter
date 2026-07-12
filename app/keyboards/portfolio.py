from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from app.utils.assets import SUPPORTED_SYMBOLS


def build_portfolio_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Add Asset")],
            [KeyboardButton(text="📋 My Portfolio")],
            [KeyboardButton(text="📊 P/L Chart")],
            [KeyboardButton(text="✏ Update Asset")],
            [KeyboardButton(text="🗑 Remove Asset")],
            [KeyboardButton(text="⬅ Back")],
        ],
        resize_keyboard=True,
    )


def build_portfolio_asset_keyboard() -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text=symbol) for symbol in SUPPORTED_SYMBOLS[index : index + 3]]
        for index in range(0, len(SUPPORTED_SYMBOLS), 3)
    ]
    buttons.append([KeyboardButton(text="⬅ Back")])
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
    )


def build_update_asset_keyboard(assets: list[str]) -> ReplyKeyboardMarkup:
    buttons = [[KeyboardButton(text=asset)] for asset in assets]
    buttons.append([KeyboardButton(text="⬅ Back")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
