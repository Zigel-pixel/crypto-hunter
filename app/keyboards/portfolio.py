from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def build_portfolio_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Add Asset")],
            [KeyboardButton(text="📋 My Portfolio")],
            [KeyboardButton(text="✏ Update Asset")],
            [KeyboardButton(text="🗑 Remove Asset")],
            [KeyboardButton(text="⬅ Back")],
        ],
        resize_keyboard=True,
    )


def build_portfolio_asset_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="BTC")],
            [KeyboardButton(text="ETH")],
            [KeyboardButton(text="SOL")],
            [KeyboardButton(text="⬅ Back")],
        ],
        resize_keyboard=True,
    )


def build_update_asset_keyboard(assets: list[str]) -> ReplyKeyboardMarkup:
    buttons = [[KeyboardButton(text=asset)] for asset in assets]
    buttons.append([KeyboardButton(text="⬅ Back")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
