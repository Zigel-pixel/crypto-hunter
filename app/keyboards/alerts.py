from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from app.services.alert_formatter import format_alert
from app.utils.i18n import SUPPORTED_LANGUAGES, translate


def alert_action_labels(key: str) -> set[str]:
    return {translate(key, language) for language in SUPPORTED_LANGUAGES}


def build_alerts_keyboard(language: str = "English") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=translate("alert.create", language))],
            [KeyboardButton(text=translate("alert.list", language))],
            [KeyboardButton(text=translate("alert.delete", language))],
            [KeyboardButton(text=translate("common.back", language))],
        ],
        resize_keyboard=True,
    )


def build_coin_selection_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="BTC")],
            [KeyboardButton(text="ETH")],
            [KeyboardButton(text="SOL")],
            [KeyboardButton(text="⬅ Back")],
        ],
        resize_keyboard=True,
    )


def build_alert_condition_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=">")],
            [KeyboardButton(text="<")],
            [KeyboardButton(text="⬅ Back")],
        ],
        resize_keyboard=True,
    )


def build_delete_alert_keyboard(alerts: list[dict[str, object]], language: str = "English") -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(text=format_alert(alert, language, delete_prefix=True)[:60], callback_data=f"alert:delete:select:{alert['id']}")] for alert in alerts[:20]]
    buttons.append([InlineKeyboardButton(text="⬅ Назад" if language == "Ukrainian" else "⬅ Back", callback_data="alert:delete:back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_delete_confirmation_keyboard(alert_id: int, language: str = "English") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Підтвердити видалення" if language == "Ukrainian" else "✅ Confirm delete", callback_data=f"alert:delete:confirm:{alert_id}")],
        [InlineKeyboardButton(text="❌ Скасувати" if language == "Ukrainian" else "❌ Cancel", callback_data="alert:delete:back")],
    ])
