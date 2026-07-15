from __future__ import annotations

from decimal import Decimal

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.handlers.message_updates import safe_update_message
from app.keyboards.main import action_labels
from app.keyboards.wallet import BACK_BUTTON, build_discovery_keyboard, build_wallet_delete_confirmation, build_wallet_detail_keyboard, build_wallet_keyboard, build_wallet_profiles_keyboard, build_wallet_selection_keyboard, wallet_action_labels
from app.services.settings_service import get_setting
from app.services.wallet_discovery_service import discover_wallet
from app.services.wallet_service import NETWORK_LABELS, delete_wallet_profile, get_wallet_profile, get_wallets_text, list_wallet_profiles, list_wallets, remove_wallet, rename_wallet_profile, save_discovered_wallet
from app.utils.i18n import normalize_language, translate

router = Router()


class WalletStates(StatesGroup):
    entering_address = State()
    confirming = State()
    selecting_wallet_to_remove = State()
    renaming = State()


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
    try:
        created, added = await save_discovered_wallet(callback.from_user.id, result)
    except ValueError as exc:
        if str(exc) == "wallet_limit_reached" and callback.message:
            await safe_update_message(callback.message, translate("wallet.limit", language), None)
        return
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
    profiles = await list_wallet_profiles(message.from_user.id)
    if profiles:
        await message.answer(_profiles_text(profiles, language), reply_markup=build_wallet_profiles_keyboard(profiles, language))
    else:
        await message.answer(await get_wallets_text(message.from_user.id), reply_markup=build_wallet_keyboard(language))


@router.callback_query(F.data == "wallet:profiles")
async def wallet_profiles(callback: types.CallbackQuery) -> None:
    await callback.answer()
    language = await _language(callback.from_user.id)
    profiles = await list_wallet_profiles(callback.from_user.id)
    if callback.message:
        await safe_update_message(callback.message, _profiles_text(profiles, language), build_wallet_profiles_keyboard(profiles, language))


@router.callback_query(F.data.startswith("wallet:profile:"))
async def wallet_profile_detail(callback: types.CallbackQuery) -> None:
    await callback.answer()
    profile_id = int((callback.data or "").rsplit(":", 1)[1])
    profile = await get_wallet_profile(callback.from_user.id, profile_id)
    language = await _language(callback.from_user.id)
    if callback.message:
        if profile is None:
            await safe_update_message(callback.message, "Гаманець не знайдено." if language == "Ukrainian" else "Wallet not found.", None)
        else:
            await safe_update_message(callback.message, _profile_text(profile, language), build_wallet_detail_keyboard(profile.id, language))


@router.callback_query(F.data.startswith(("wallet:refresh:", "wallet:profile_rescan:")))
async def refresh_profile(callback: types.CallbackQuery) -> None:
    await callback.answer("Updating…")
    profile_id = int((callback.data or "").rsplit(":", 1)[1])
    profile = await get_wallet_profile(callback.from_user.id, profile_id)
    language = await _language(callback.from_user.id)
    if profile is None or callback.message is None:
        return
    result = await discover_wallet(profile.address, bypass_cooldown=True)
    _, added = await save_discovered_wallet(callback.from_user.id, result)
    profile = await get_wallet_profile(callback.from_user.id, profile_id)
    suffix = (f"\n\nNew networks: {added}" if added else "") if language == "English" else (f"\n\nНових мереж: {added}" if added else "")
    await safe_update_message(callback.message, _format_discovery(result, language) + suffix, build_wallet_detail_keyboard(profile_id, language))


@router.callback_query(F.data.startswith("wallet:rename:"))
async def rename_profile_entry(callback: types.CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    profile_id = int((callback.data or "").rsplit(":", 1)[1])
    if await get_wallet_profile(callback.from_user.id, profile_id) is None:
        return
    await state.update_data(profile_id=profile_id)
    await state.set_state(WalletStates.renaming)
    if callback.message:
        language = await _language(callback.from_user.id)
        await callback.message.answer("Введіть нову назву (1–40 символів):" if language == "Ukrainian" else "Enter a new label (1–40 characters):")


@router.message(WalletStates.renaming)
async def rename_profile(message: types.Message, state: FSMContext) -> None:
    profile_id = (await state.get_data()).get("profile_id")
    language = await _language(message.from_user.id)
    try:
        updated = isinstance(profile_id, int) and await rename_wallet_profile(message.from_user.id, profile_id, message.text or "")
    except ValueError:
        await message.answer("Назва має містити 1–40 символів." if language == "Ukrainian" else "The label must contain 1–40 characters.")
        return
    await state.clear()
    await message.answer(("✅ Гаманець перейменовано." if language == "Ukrainian" else "✅ Wallet renamed.") if updated else ("Гаманець не знайдено." if language == "Ukrainian" else "Wallet not found."), reply_markup=build_wallet_keyboard(language))


@router.callback_query(F.data.startswith("wallet:profile_delete:"))
async def delete_profile_prompt(callback: types.CallbackQuery) -> None:
    await callback.answer()
    profile_id = int((callback.data or "").rsplit(":", 1)[1])
    profile = await get_wallet_profile(callback.from_user.id, profile_id)
    language = await _language(callback.from_user.id)
    if callback.message and profile:
        await safe_update_message(callback.message, ("Видалити цей гаманець?" if language == "Ukrainian" else "Delete this wallet?") + "\n\n" + _profile_text(profile, language), build_wallet_delete_confirmation(profile_id, language))


@router.callback_query(F.data.startswith("wallet:profile_delete_confirm:"))
async def delete_profile_confirm(callback: types.CallbackQuery) -> None:
    await callback.answer()
    profile_id = int((callback.data or "").rsplit(":", 1)[1])
    deleted = await delete_wallet_profile(callback.from_user.id, profile_id)
    language = await _language(callback.from_user.id)
    if callback.message:
        text = ("✅ Гаманець видалено." if language == "Ukrainian" else "✅ Wallet deleted.") if deleted else ("ℹ️ Гаманець уже видалено." if language == "Ukrainian" else "ℹ️ Wallet was already deleted.")
        await safe_update_message(callback.message, text, None)


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


def _profiles_text(profiles, language: str) -> str:
    if not profiles:
        return "Гаманців ще немає." if language == "Ukrainian" else "No wallets added yet."
    lines = ["👛 Гаманці" if language == "Ukrainian" else "👛 Wallets", ""]
    for item in profiles:
        lines.extend([f"💼 {item.label or 'Wallet'}", f"{item.address[:6]}…{item.address[-4:]}", f"{item.address_family.upper()} · {' • '.join(item.networks) or '—'}", ""])
    return "\n".join(lines).rstrip()


def _profile_text(profile, language: str) -> str:
    native = f"{_format_decimal(profile.native_balance)} {profile.native_symbol}" if profile.native_balance is not None else "—"
    usdt = f"{_format_decimal(profile.usdt_balance)} USDT" if profile.usdt_balance is not None else "—"
    status = translate("wallet.stale", language) if profile.balance_status == "stale" else translate("wallet.updated", language)
    return "\n".join([
        f"💼 {profile.label or ('Гаманець' if language == 'Ukrainian' else 'Wallet')}",
        "", f"Address: {profile.address}", f"Network: {' • '.join(profile.networks) or '—'}",
        f"Native: {native}", f"USDT: {usdt}",
        f"{status}: {profile.last_success_at or '—'}",
    ])


def _format_decimal(value: str | None) -> str:
    if value is None:
        return "—"
    rendered = format(Decimal(value), "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered or "0"
