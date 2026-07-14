from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

DEFAULT_LANGUAGE = "English"
SUPPORTED_LANGUAGES = ("English", "Ukrainian")

_TRANSLATIONS: dict[str, dict[str, str]] = {
    "English": {
        "menu.rates": "📈 Rates", "menu.watchlist": "⭐ Watchlist",
        "menu.alerts": "🔔 Alerts", "menu.news": "📰 News",
        "menu.portfolio": "💼 Portfolio", "menu.wallets": "👛 Wallets",
        "menu.assets": "📊 Assets", "menu.consultant": "🤖 AI Consultant",
        "menu.settings": "⚙ Settings", "controls.start": "▶️ Start",
        "controls.restart": "🔄 Restart", "controls.stop": "⏹ Stop",
        "common.back": "⬅ Back", "common.refresh": "🔄 Refresh",
        "session.started": "🏠 Crypto Hunter\n\nYour session is active.",
        "session.restarted": "🔄 Your Crypto Hunter session has been restarted.",
        "session.stopped": "⏹ Crypto Hunter is stopped for your account. Press ▶️ Start or send /start to continue.",
        "session.unavailable": "Session service is temporarily unavailable.",
        "news.title": "📰 Latest crypto news", "news.unavailable": "❌ Could not load news. Please try again later.",
        "news.source": "Source: CoinDesk", "news.refresh": "🔄 Refresh News",
    },
    "Ukrainian": {
        "menu.rates": "📈 Курси", "menu.watchlist": "⭐ Обране",
        "menu.alerts": "🔔 Сповіщення", "menu.news": "📰 Новини",
        "menu.portfolio": "💼 Портфель", "menu.wallets": "👛 Гаманці",
        "menu.assets": "📊 Активи", "menu.consultant": "🤖 AI Консультант",
        "menu.settings": "⚙ Налаштування", "controls.start": "▶️ Старт",
        "controls.restart": "🔄 Перезапустити", "controls.stop": "⏹ Зупинити",
        "common.back": "⬅ Назад", "common.refresh": "🔄 Оновити",
        "session.started": "🏠 Crypto Hunter\n\nВаш сеанс активний.",
        "session.restarted": "🔄 Ваш сеанс Crypto Hunter перезапущено.",
        "session.stopped": "⏹ Crypto Hunter зупинено для вашого облікового запису. Натисніть ▶️ Старт або надішліть /start, щоб продовжити.",
        "session.unavailable": "Сервіс сеансів тимчасово недоступний.",
        "news.title": "📰 Останні криптоновини", "news.unavailable": "❌ Не вдалося завантажити новини. Спробуйте трохи пізніше.",
        "news.source": "Джерело: CoinDesk", "news.refresh": "🔄 Оновити новини",
    },
}


def normalize_language(language: str | None) -> str:
    return language if language in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def translate(key: str, language: str | None = None) -> str:
    selected = normalize_language(language)
    value = _TRANSLATIONS[selected].get(key) or _TRANSLATIONS[DEFAULT_LANGUAGE].get(key)
    if value is None:
        logger.warning("Missing translation key: %s", key)
        return key
    return value
