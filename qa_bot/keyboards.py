from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

LABELS = {
    "smoke": "▶️ Run smoke tests", "all": "🧪 Run full QA", "localization": "🌐 Localization",
    "live": "📈 Live charts", "favorites": "⭐ Favorites", "alerts": "🔔 Alerts",
    "ai": "🤖 AI consultant", "wallets": "👛 Wallets", "report": "📄 Last report",
    "prompt": "🧠 Codex prompt", "status": "ℹ️ Status", "cancel": "⛔ Cancel",
}


def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=LABELS["smoke"], callback_data="qa:run:smoke"), InlineKeyboardButton(text=LABELS["all"], callback_data="qa:run:all")],
        [InlineKeyboardButton(text=LABELS[name], callback_data=f"qa:run:{name}") for name in ("localization", "live")],
        [InlineKeyboardButton(text=LABELS[name], callback_data=f"qa:run:{name}") for name in ("favorites", "alerts")],
        [InlineKeyboardButton(text=LABELS[name], callback_data=f"qa:run:{name}") for name in ("ai", "wallets")],
        [InlineKeyboardButton(text=LABELS["report"], callback_data="qa:last"), InlineKeyboardButton(text=LABELS["prompt"], callback_data="qa:prompt")],
        [InlineKeyboardButton(text=LABELS["status"], callback_data="qa:status"), InlineKeyboardButton(text=LABELS["cancel"], callback_data="qa:cancel")],
    ])


def clear_confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Clear generated reports", callback_data="qa:clear:confirm")], [InlineKeyboardButton(text="❌ Cancel", callback_data="qa:clear:cancel")]])
