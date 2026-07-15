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
        "wallet.title": "👛 Wallets", "wallet.add": "➕ Add wallet",
        "wallet.list": "📋 My wallets", "wallet.remove": "🗑 Delete wallet",
        "wallet.warning": "⚠️ Send only a public wallet address. Never send a seed phrase or private key.",
        "wallet.invalid": "❌ This wallet address is invalid or its network is not supported yet.",
        "wallet.scanning": "🔎 Scanning compatible networks…", "wallet.scan_complete": "🔎 Wallet scan complete",
        "wallet.confirm": "✅ Add all active networks", "wallet.scan_again": "🔄 Scan again", "common.cancel": "❌ Cancel",
        "wallet.limit": "❌ Wallet limit reached.", "wallet.stale": "⚠️ Stale data", "wallet.updated": "Updated",
        "wallet.singular": "Wallet", "wallet.address": "Address", "wallet.network": "Network",
        "wallet.native_balance": "Native balance", "wallet.usdt_balance": "USDT balance",
        "wallet.detected_network": "Detected network",
        "wallet.error.provider_not_configured": "This network provider is not configured.",
        "wallet.error.invalid_address": "The wallet address is invalid.",
        "wallet.error.timeout": "The provider timed out. Try again later.",
        "wallet.error.rate_limited": "The provider rate limit was reached. Try again later.",
        "wallet.error.provider_unavailable": "The balance provider is temporarily unavailable.",
        "wallet.error.malformed_response": "The provider returned an invalid response.",
        "wallet.error.unsupported_network": "This network is not supported.",
        "wallet.error.contract_error": "The token contract request failed.",
        "wallet.error.unknown_provider_error": "The balance could not be updated.",
        "consultant.market": "📊 Market Analysis", "consultant.wallet": "👛 Analyze Wallets", "consultant.ask": "💬 Ask Consultant",
        "alert.create": "➕ Create Alert", "alert.list": "📋 My Alerts", "alert.delete": "🗑 Delete Alert",
        "settings.title": "⚙ Settings", "settings.language": "🌐 Language",
        "settings.currency": "💱 Currency", "settings.timezone": "🕒 Timezone",
        "settings.choose_language": "Choose language:", "language.ukrainian": "Ukrainian",
        "language.english": "English", "settings.language_saved": "✅ Language changed to English.",
        "settings.choose_currency": "Choose currency:",
        "settings.choose_timezone": "Choose a timezone or send an IANA name, for example Europe/Paris or Asia/Dubai:",
        "settings.updated": "✅ Settings updated.", "settings.unknown_timezone": "Unknown timezone. Use an IANA name such as Europe/Kyiv or Asia/Shanghai.",
        "settings.returned": "↩ Returned to the main menu.",
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
        "wallet.title": "👛 Гаманці", "wallet.add": "➕ Додати гаманець",
        "wallet.list": "📋 Мої гаманці", "wallet.remove": "🗑 Видалити гаманець",
        "wallet.warning": "⚠️ Надсилайте лише публічну адресу гаманця. Ніколи не надсилайте seed-фразу або приватний ключ.",
        "wallet.invalid": "❌ Ця адреса гаманця некоректна або її мережа поки не підтримується.",
        "wallet.scanning": "🔎 Перевіряємо сумісні мережі…", "wallet.scan_complete": "🔎 Перевірку гаманця завершено",
        "wallet.confirm": "✅ Додати всі активні мережі", "wallet.scan_again": "🔄 Сканувати знову", "common.cancel": "❌ Скасувати",
        "wallet.limit": "❌ Досягнуто ліміту гаманців.", "wallet.stale": "⚠️ Застарілі дані", "wallet.updated": "Оновлено",
        "wallet.singular": "Гаманець", "wallet.address": "Адреса", "wallet.network": "Мережа",
        "wallet.native_balance": "Нативний баланс", "wallet.usdt_balance": "Баланс USDT",
        "wallet.detected_network": "Визначена мережа",
        "wallet.error.provider_not_configured": "Провайдер цієї мережі не налаштований.",
        "wallet.error.invalid_address": "Адреса гаманця некоректна.",
        "wallet.error.timeout": "Провайдер не відповів вчасно. Спробуйте пізніше.",
        "wallet.error.rate_limited": "Досягнуто ліміту запитів провайдера. Спробуйте пізніше.",
        "wallet.error.provider_unavailable": "Провайдер балансів тимчасово недоступний.",
        "wallet.error.malformed_response": "Провайдер повернув некоректну відповідь.",
        "wallet.error.unsupported_network": "Ця мережа не підтримується.",
        "wallet.error.contract_error": "Не вдалося виконати запит до контракту токена.",
        "wallet.error.unknown_provider_error": "Не вдалося оновити баланс.",
        "consultant.market": "📊 Аналіз ринку", "consultant.wallet": "👛 Аналіз гаманців", "consultant.ask": "💬 Запитати консультанта",
        "alert.create": "➕ Створити сповіщення", "alert.list": "📋 Мої сповіщення", "alert.delete": "🗑 Видалити сповіщення",
        "settings.title": "⚙ Налаштування", "settings.language": "🌐 Мова",
        "settings.currency": "💱 Валюта", "settings.timezone": "🕒 Часовий пояс",
        "settings.choose_language": "Оберіть мову:", "language.ukrainian": "Українська",
        "language.english": "Англійська", "settings.language_saved": "✅ Мову змінено на українську.",
        "settings.choose_currency": "Оберіть валюту:",
        "settings.choose_timezone": "Оберіть часовий пояс або надішліть назву IANA, наприклад Europe/Kyiv чи Asia/Dubai:",
        "settings.updated": "✅ Налаштування оновлено.", "settings.unknown_timezone": "Невідомий часовий пояс. Використайте назву IANA, наприклад Europe/Kyiv або Asia/Shanghai.",
        "settings.returned": "↩ Повернулися до головного меню.",
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
