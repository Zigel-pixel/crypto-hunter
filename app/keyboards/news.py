from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from app.utils.i18n import SUPPORTED_LANGUAGES, translate

REFRESH_NEWS_BUTTON = "🔄 Refresh News"
BACK_BUTTON = "⬅ Back"


def news_action_labels(key: str) -> set[str]:
    return {translate(key, language) for language in SUPPORTED_LANGUAGES}


def build_news_keyboard(language: str = "English") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=translate("news.refresh", language))],
            [KeyboardButton(text=translate("common.back", language))],
        ],
        resize_keyboard=True,
    )

