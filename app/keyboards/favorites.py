from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def build_favorites_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Add Coin")],
            [KeyboardButton(text="📋 My Favorites")],
            [KeyboardButton(text="🗑 Remove Coin")],
            [KeyboardButton(text="⬅ Back")],
        ],
        resize_keyboard=True,
    )


def build_coin_selection_keyboard(coins: list[str]) -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text=coin) for coin in coins[index : index + 2]]
        for index in range(0, len(coins), 2)
    ]
    buttons.append([KeyboardButton(text="⬅ Back")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def build_remove_selection_keyboard(coins: list[str]) -> ReplyKeyboardMarkup:
    buttons = [[KeyboardButton(text=coin)] for coin in coins]
    buttons.append([KeyboardButton(text="⬅ Back")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
