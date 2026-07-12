from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

REFRESH_NEWS_BUTTON = "🔄 Refresh News"
BACK_BUTTON = "⬅ Back"


def build_news_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=REFRESH_NEWS_BUTTON)],
            [KeyboardButton(text=BACK_BUTTON)],
        ],
        resize_keyboard=True,
    )

