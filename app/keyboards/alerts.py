from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def build_alerts_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Create Alert")],
            [KeyboardButton(text="📋 My Alerts")],
            [KeyboardButton(text="🗑 Delete Alert")],
            [KeyboardButton(text="⬅ Back")],
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


def build_delete_alert_keyboard(alerts: list[dict[str, object]]) -> ReplyKeyboardMarkup:
    buttons = [[KeyboardButton(text=str(alert["id"]))] for alert in alerts]
    buttons.append([KeyboardButton(text="⬅ Back")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
