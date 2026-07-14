from __future__ import annotations

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.handlers.message_updates import safe_update_message
from app.keyboards.main import action_labels
from app.keyboards.wallet import BACK_BUTTON, build_discovery_keyboard, build_wallet_keyboard, build_wallet_selection_keyboard, wallet_action_labels
from app.services.settings_service import get_setting
from app.services.wallet_discovery_service import discover_wallet
from app.services.wallet_service import NETWORK_LABELS, get_wallets_text, list_wallets, remove_wallet, save_discovered_wallet
from app.utils.i18n import normalize_language, translate

router = Router()


class WalletStates(StatesGroup):
    entering_address = State()
    confirming = State()
    selecting_wallet_to_remove = State()


async def _language(user_id: int) -> str:
    return normalize_language(await get_setting(user_id, "language"))


@router.message(lambda message: message.text in action_labels(5))
async def wallets_entry(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    language = await _language(message.from_user.id)
    await message.answer(translate("wallet.title", language), reply_markup=build_wallet_keyboard(language))


@router.message(lambda message: message.text in wallet_action_labels("wallet.add"))
async def add_wallet_entry(message: types.Message, state: FSMContext) -> None:
    await state.set_state(WalletStates.entering_address)
    language = await _language(message.from_user.id)
    await message.answer(translate("wallet.warning", language), reply_markup=build_wallet_keyboard(language))


@router.message(WalletStates.entering_address)
async def scan_wallet(message: types.Message, state: FSMContext) -> None:
    language = await _language(message.from_user.id)
    value = (message.text or "").strip()
    await message.answer(translate("wallet.scanning", language))
    try:
        result = await discover_wallet(value)
    except (ValueError, RuntimeError):
        await message.answer(translate("wallet.invalid", language))
        return
    await state.update_data(wallet_address=result.address.display_address)
    await state.set_state(WalletStates.confirming)
    await message.answer(_format_discovery(result, language), reply_markup=build_discovery_keyboard(language))


@router.callback_query(F.data == "wallet:confirm", WalletStates.confirming)
async def confirm_wallet(callback: types.CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    language = await _language(callback.from_user.id)
    address = (await state.get_data()).get("wallet_address")
    if not isinstance(address, str):
        await state.clear()
        return
    result = await discover_wallet(address, bypass_cooldown=True)
    created, added = await save_discovered_wallet(callback.from_user.id, result)
    await state.clear()
    text = "✅ Wallet added." if created else ("✅ Existing wallet updated." if added else "ℹ️ This wallet is already saved.")
    if language == "Ukrainian":
        text = "✅ Гаманець додано." if created else ("✅ Існуючий гаманець оновлено." if added else "ℹ️ Цей гаманець уже збережено.")
    if callback.message:
        await safe_update_message(callback.message, text, None)


@router.callback_query(F.data == "wallet:rescan", WalletStates.confirming)
async def rescan_wallet(callback: types.CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    language = await _language(callback.from_user.id)
    address = (await state.get_data()).get("wallet_address")
    if isinstance(address, str) and callback.message:
        result = await discover_wallet(address, bypass_cooldown=True)
        await safe_update_message(callback.message, _format_discovery(result, language), build_discovery_keyboard(language))


@router.callback_query(F.data == "wallet:cancel")
async def cancel_wallet(callback: types.CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    if callback.message:
        await safe_update_message(callback.message, translate("wallet.title", await _language(callback.from_user.id)), None)


@router.message(lambda message: message.text in wallet_action_labels("wallet.list"))
async def my_wallets(message: types.Message) -> None:
    language = await _language(message.from_user.id)
    await message.answer(await get_wallets_text(message.from_user.id), reply_markup=build_wallet_keyboard(language))


@router.message(lambda message: message.text in wallet_action_labels("wallet.remove"))
async def remove_wallet_entry(message: types.Message, state: FSMContext) -> None:
    language = await _language(message.from_user.id)
    wallets = await list_wallets(message.from_user.id)
    if not wallets:
        await message.answer("No wallets added yet." if language == "English" else "Гаманців ще немає.", reply_markup=build_wallet_keyboard(language))
        return
    choices = {f"{NETWORK_LABELS[item.network]}: {item.address}": (item.network, item.address) for item in wallets}
    await state.update_data(wallet_choices=choices)
    await state.set_state(WalletStates.selecting_wallet_to_remove)
    await message.answer("Select a wallet to delete:" if language == "English" else "Оберіть гаманець для видалення:", reply_markup=build_wallet_selection_keyboard(wallets, NETWORK_LABELS))


@router.message(WalletStates.selecting_wallet_to_remove)
async def remove_selected_wallet(message: types.Message, state: FSMContext) -> None:
    language = await _language(message.from_user.id)
    choices = (await state.get_data()).get("wallet_choices", {})
    selected = choices.get(message.text) if isinstance(choices, dict) else None
    if not selected:
        await message.answer("Please select a wallet from the list." if language == "English" else "Оберіть гаманець зі списку.")
        return
    removed = await remove_wallet(message.from_user.id, selected[0], selected[1])
    await state.clear()
    text = ("✅ Wallet deleted." if language == "English" else "✅ Гаманець видалено.") if removed else translate("wallet.invalid", language)
    await message.answer(text, reply_markup=build_wallet_keyboard(language))


def _format_discovery(result, language: str) -> str:
    lines = [translate("wallet.scan_complete", language), f"Address: {result.address.display_address[:6]}…{result.address.display_address[-4:]}", ""]
    for snapshot in result.active:
        lines.append(snapshot.chain.replace("_", " ").title())
        for asset in snapshot.assets:
            label = f"{asset.symbol} ({asset.standard})" if asset.standard else asset.symbol
            lines.append(f"• {label}: {asset.amount:,.8f}".rstrip("0").rstrip("."))
        lines.append("")
    if not result.active:
        count = len(result.scanned_networks)
        lines.append(f"✅ Wallet scanned across {count} networks. No supported balances were found." if language == "English" else f"✅ Гаманець перевірено у {count} мережах. Підтримуваних балансів не знайдено.")
    if result.warnings:
        lines.append(("⚠️ Partial provider failure: " if language == "English" else "⚠️ Частина провайдерів недоступна: ") + ", ".join(result.warnings))
    return "\n".join(lines).rstrip()
