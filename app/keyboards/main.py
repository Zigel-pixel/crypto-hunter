from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def build_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📈 Rates"), KeyboardButton(text="⭐ Favorites")],
            [KeyboardButton(text="🔔 Alerts"), KeyboardButton(text="📰 News")],
            [KeyboardButton(text="💼 Portfolio"), KeyboardButton(text="👛 Wallets")],
            [KeyboardButton(text="⚙ Settings")],
        ],
        resize_keyboard=True,
    )
