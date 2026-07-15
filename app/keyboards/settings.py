from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from app.utils.i18n import translate


def build_settings_keyboard(language: str = "English") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=translate("settings.language", language))],
            [KeyboardButton(text=translate("settings.currency", language))],
            [KeyboardButton(text=translate("settings.timezone", language))],
            [KeyboardButton(text=translate("common.back", language))],
        ],
        resize_keyboard=True,
    )


def build_language_keyboard(language: str = "English") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=translate("language.ukrainian", language))],
            [KeyboardButton(text=translate("language.english", language))],
            [KeyboardButton(text=translate("common.back", language))],
        ],
        resize_keyboard=True,
    )


def build_currency_keyboard(language: str = "English") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="USD")],
            [KeyboardButton(text="EUR")],
            [KeyboardButton(text="UAH")],
            [KeyboardButton(text=translate("common.back", language))],
        ],
        resize_keyboard=True,
    )


def build_timezone_keyboard(language: str = "English") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="UTC"), KeyboardButton(text="Europe/Kyiv")],
            [KeyboardButton(text="Europe/London"), KeyboardButton(text="America/New_York")],
            [KeyboardButton(text="Asia/Shanghai"), KeyboardButton(text="Asia/Tokyo")],
            [KeyboardButton(text=translate("common.back", language))],
        ],
        resize_keyboard=True,
    )
