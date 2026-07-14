from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from app.utils.i18n import SUPPORTED_LANGUAGES, translate

_MENU_KEYS = (
    "menu.rates", "menu.watchlist", "menu.alerts", "menu.news",
    "menu.portfolio", "menu.wallets", "menu.consultant", "menu.settings",
)


def action_labels(index: int) -> set[str]:
    return {translate(_MENU_KEYS[index], language) for language in SUPPORTED_LANGUAGES}


def control_labels(key: str) -> set[str]:
    return {translate(key, language) for language in SUPPORTED_LANGUAGES}


def build_main_keyboard(language: str = "English") -> ReplyKeyboardMarkup:
    labels = [translate(key, language) for key in _MENU_KEYS]
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=labels[0]), KeyboardButton(text=labels[1])],
            [KeyboardButton(text=labels[2]), KeyboardButton(text=labels[3])],
            [KeyboardButton(text=labels[4]), KeyboardButton(text=labels[5])],
            [KeyboardButton(text=translate("menu.assets", language))],
            [KeyboardButton(text=labels[6])], [KeyboardButton(text=labels[7])],
            [KeyboardButton(text=translate("controls.start", language)), KeyboardButton(text=translate("controls.restart", language)), KeyboardButton(text=translate("controls.stop", language))],
        ], resize_keyboard=True,
    )


def build_stopped_keyboard(language: str = "English") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=translate("controls.start", language))]],
        resize_keyboard=True,
    )
