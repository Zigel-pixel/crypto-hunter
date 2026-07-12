from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def build_settings_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🌐 Language")],
            [KeyboardButton(text="💱 Currency")],
            [KeyboardButton(text="🕒 Timezone")],
            [KeyboardButton(text="⬅ Back")],
        ],
        resize_keyboard=True,
    )


def build_language_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Ukrainian")],
            [KeyboardButton(text="English")],
            [KeyboardButton(text="Russian")],
            [KeyboardButton(text="Chinese")],
            [KeyboardButton(text="⬅ Back")],
        ],
        resize_keyboard=True,
    )


def build_currency_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="USD")],
            [KeyboardButton(text="EUR")],
            [KeyboardButton(text="UAH")],
            [KeyboardButton(text="⬅ Back")],
        ],
        resize_keyboard=True,
    )


def build_timezone_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="UTC"), KeyboardButton(text="Europe/Kyiv")],
            [KeyboardButton(text="Europe/London"), KeyboardButton(text="America/New_York")],
            [KeyboardButton(text="Asia/Shanghai"), KeyboardButton(text="Asia/Tokyo")],
            [KeyboardButton(text="⬅ Back")],
        ],
        resize_keyboard=True,
    )
