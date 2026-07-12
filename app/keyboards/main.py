from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

MAIN_LABELS = {
    "English": ("📈 Rates", "⭐ Favorites", "🔔 Alerts", "📰 News", "💼 Portfolio", "👛 Wallets", "🤖 AI Consultant", "⚙ Settings"),
    "Ukrainian": ("📈 Курси", "⭐ Обране", "🔔 Alerts", "📰 Новини", "💼 Портфель", "👛 Гаманці", "🤖 AI Консультант", "⚙ Налаштування"),
    "Russian": ("📈 Курсы", "⭐ Избранное", "🔔 Alerts", "📰 Новости", "💼 Портфель", "👛 Кошельки", "🤖 AI Консультант", "⚙ Настройки"),
    "Chinese": ("📈 行情", "⭐ 收藏", "🔔 Alerts", "📰 新闻", "💼 投资组合", "👛 钱包", "🤖 AI 顾问", "⚙ 设置"),
}


def action_labels(index: int) -> set[str]:
    return {labels[index] for labels in MAIN_LABELS.values()}


def build_main_keyboard(language: str = "English") -> ReplyKeyboardMarkup:
    labels = MAIN_LABELS.get(language, MAIN_LABELS["English"])
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=labels[0]), KeyboardButton(text=labels[1])],
            [KeyboardButton(text=labels[2]), KeyboardButton(text=labels[3])],
            [KeyboardButton(text=labels[4]), KeyboardButton(text=labels[5])],
            [KeyboardButton(text=labels[6])],
            [KeyboardButton(text=labels[7])],
        ],
        resize_keyboard=True,
    )
