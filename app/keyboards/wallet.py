from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from app.models.wallet import StoredWallet

ADD_WALLET_BUTTON = "➕ Add Wallet"
MY_WALLETS_BUTTON = "📋 My Wallets"
REMOVE_WALLET_BUTTON = "🗑 Remove Wallet"
BACK_BUTTON = "⬅ Back"


def build_wallet_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=ADD_WALLET_BUTTON)],
            [KeyboardButton(text=MY_WALLETS_BUTTON)],
            [KeyboardButton(text=REMOVE_WALLET_BUTTON)],
            [KeyboardButton(text=BACK_BUTTON)],
        ],
        resize_keyboard=True,
    )


def build_network_keyboard(network_labels: dict[str, str]) -> ReplyKeyboardMarkup:
    buttons = [[KeyboardButton(text=label)] for label in network_labels.values()]
    buttons.append([KeyboardButton(text=BACK_BUTTON)])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def build_wallet_selection_keyboard(
    wallets: list[StoredWallet], network_labels: dict[str, str]
) -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text=f"{network_labels[wallet.network]}: {wallet.address}")]
        for wallet in wallets
    ]
    buttons.append([KeyboardButton(text=BACK_BUTTON)])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
