from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

CONSULTANT_BUTTON = "🤖 AI Consultant"
MARKET_ANALYSIS_BUTTON = "📊 Market Analysis"
WALLET_ANALYSIS_BUTTON = "👛 Analyze Wallets"
ASK_CONSULTANT_BUTTON = "💬 Ask Consultant"
BACK_BUTTON = "⬅ Back"


def build_consultant_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=MARKET_ANALYSIS_BUTTON)],
            [KeyboardButton(text=WALLET_ANALYSIS_BUTTON)],
            [KeyboardButton(text=ASK_CONSULTANT_BUTTON)],
            [KeyboardButton(text=BACK_BUTTON)],
        ],
        resize_keyboard=True,
    )

