from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from app.utils.i18n import SUPPORTED_LANGUAGES, translate

CONSULTANT_BUTTON = "🤖 AI Consultant"
MARKET_ANALYSIS_BUTTON = "📊 Market Analysis"
WALLET_ANALYSIS_BUTTON = "👛 Analyze Wallets"
ASK_CONSULTANT_BUTTON = "💬 Ask Consultant"
BACK_BUTTON = "⬅ Back"

KEYS = {"market": "consultant.market", "wallet": "consultant.wallet", "ask": "consultant.ask", "back": "common.back"}


def consultant_labels(name: str) -> set[str]:
    return {translate(KEYS[name], language) for language in SUPPORTED_LANGUAGES}


def build_consultant_keyboard(language: str = "English") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=translate("consultant.market", language))],
        [KeyboardButton(text=translate("consultant.wallet", language))],
        [KeyboardButton(text=translate("consultant.ask", language))],
        [KeyboardButton(text=translate("common.back", language))],
    ], resize_keyboard=True)
