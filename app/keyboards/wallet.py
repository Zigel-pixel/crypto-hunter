from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from app.models.wallet import StoredWallet, WalletProfile
from app.utils.i18n import SUPPORTED_LANGUAGES, translate

ADD_WALLET_BUTTON = "➕ Add Wallet"
MY_WALLETS_BUTTON = "📋 My Wallets"
REMOVE_WALLET_BUTTON = "🗑 Remove Wallet"
BACK_BUTTON = "⬅ Back"


def wallet_action_labels(key: str) -> set[str]:
    return {translate(key, language) for language in SUPPORTED_LANGUAGES}


def build_wallet_keyboard(language: str = "English") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=translate("wallet.add", language))],
        [KeyboardButton(text=translate("wallet.list", language)), KeyboardButton(text=translate("wallet.remove", language))],
        [KeyboardButton(text=translate("common.back", language))],
    ], resize_keyboard=True)


def build_discovery_keyboard(language: str = "English") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=translate("wallet.confirm", language), callback_data="wallet:confirm")],
        [InlineKeyboardButton(text=translate("wallet.scan_again", language), callback_data="wallet:rescan")],
        [InlineKeyboardButton(text=translate("common.cancel", language), callback_data="wallet:cancel")],
    ])


def build_network_keyboard(network_labels: dict[str, str]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=x)] for x in (*network_labels.values(), BACK_BUTTON)], resize_keyboard=True)


def build_wallet_selection_keyboard(wallets: list[StoredWallet], network_labels: dict[str, str]) -> ReplyKeyboardMarkup:
    buttons = [[KeyboardButton(text=f"{network_labels[wallet.network]}: {wallet.address}")] for wallet in wallets]
    buttons.append([KeyboardButton(text=BACK_BUTTON)])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def build_wallet_profiles_keyboard(profiles: list[WalletProfile], language: str = "English") -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=f"💼 {item.label or item.address[:6] + '…' + item.address[-4:]}", callback_data=f"wallet:profile:{item.id}")] for item in profiles]
    rows.append([InlineKeyboardButton(text=translate("common.back", language), callback_data="wallet:profiles:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_wallet_detail_keyboard(profile_id: int, language: str = "English") -> InlineKeyboardMarkup:
    uk = language == "Ukrainian"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Оновити баланси" if uk else "🔄 Refresh balances", callback_data=f"wallet:refresh:{profile_id}")],
        [InlineKeyboardButton(text="🔎 Пересканувати мережі" if uk else "🔎 Rescan networks", callback_data=f"wallet:profile_rescan:{profile_id}")],
        [InlineKeyboardButton(text="✏️ Перейменувати" if uk else "✏️ Rename", callback_data=f"wallet:rename:{profile_id}")],
        [InlineKeyboardButton(text="🗑 Видалити" if uk else "🗑 Delete", callback_data=f"wallet:profile_delete:{profile_id}")],
        [InlineKeyboardButton(text=translate("common.back", language), callback_data="wallet:profiles")],
    ])


def build_wallet_delete_confirmation(profile_id: int, language: str = "English") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Видалити" if language == "Ukrainian" else "✅ Delete", callback_data=f"wallet:profile_delete_confirm:{profile_id}")],
        [InlineKeyboardButton(text=translate("common.cancel", language), callback_data=f"wallet:profile:{profile_id}")],
    ])
