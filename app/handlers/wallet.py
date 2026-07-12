from __future__ import annotations

from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.keyboards.main import build_main_keyboard
from app.keyboards.wallet import (
    ADD_WALLET_BUTTON,
    BACK_BUTTON,
    MY_WALLETS_BUTTON,
    REMOVE_WALLET_BUTTON,
    build_network_keyboard,
    build_wallet_keyboard,
    build_wallet_selection_keyboard,
)
from app.services.wallet_service import (
    NETWORK_LABELS,
    add_wallet,
    get_wallets_text,
    list_wallets,
    remove_wallet,
)

WALLETS_MENU_BUTTON = "👛 Wallets"
NETWORK_BY_LABEL = {label: network for network, label in NETWORK_LABELS.items()}

router = Router()


class WalletStates(StatesGroup):
    choosing_network = State()
    entering_address = State()
    selecting_wallet_to_remove = State()


@router.message(lambda message: message.text == WALLETS_MENU_BUTTON)
async def wallets_entry(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("👛 Wallets", reply_markup=build_wallet_keyboard())


@router.message(lambda message: message.text == ADD_WALLET_BUTTON)
async def add_wallet_entry(message: types.Message, state: FSMContext) -> None:
    await state.set_state(WalletStates.choosing_network)
    await message.answer(
        "Choose a network:", reply_markup=build_network_keyboard(NETWORK_LABELS)
    )


@router.message(
    lambda message: message.text in NETWORK_BY_LABEL,
    WalletStates.choosing_network,
)
async def choose_network(message: types.Message, state: FSMContext) -> None:
    network = NETWORK_BY_LABEL[message.text]
    await state.update_data(network=network)
    await state.set_state(WalletStates.entering_address)
    await message.answer("Send the wallet address:")


@router.message(
    lambda message: message.text != BACK_BUTTON,
    WalletStates.entering_address,
)
async def save_wallet_address(message: types.Message, state: FSMContext) -> None:
    data = await state.get_data()
    network = data.get("network")
    address = (message.text or "").strip()
    if not isinstance(network, str):
        await state.clear()
        await message.answer("❌ Unable to add wallet.", reply_markup=build_wallet_keyboard())
        return

    try:
        added = await add_wallet(message.from_user.id, network, address)
    except ValueError:
        await message.answer("❌ Invalid address for the selected network. Try again.")
        return

    await state.clear()
    if added:
        await message.answer("✅ Wallet added.", reply_markup=build_wallet_keyboard())
    else:
        await message.answer("ℹ️ This wallet is already saved.", reply_markup=build_wallet_keyboard())


@router.message(lambda message: message.text == MY_WALLETS_BUTTON)
async def my_wallets(message: types.Message) -> None:
    text = await get_wallets_text(message.from_user.id)
    await message.answer(text, reply_markup=build_wallet_keyboard())


@router.message(lambda message: message.text == REMOVE_WALLET_BUTTON)
async def remove_wallet_entry(message: types.Message, state: FSMContext) -> None:
    wallets = await list_wallets(message.from_user.id)
    if not wallets:
        await message.answer("No wallets added yet.", reply_markup=build_wallet_keyboard())
        return

    choices = {
        f"{NETWORK_LABELS[wallet.network]}: {wallet.address}": {
            "network": wallet.network,
            "address": wallet.address,
        }
        for wallet in wallets
    }
    await state.update_data(wallet_choices=choices)
    await state.set_state(WalletStates.selecting_wallet_to_remove)
    await message.answer(
        "Select a wallet to remove:",
        reply_markup=build_wallet_selection_keyboard(wallets, NETWORK_LABELS),
    )


@router.message(
    lambda message: message.text != BACK_BUTTON,
    WalletStates.selecting_wallet_to_remove,
)
async def remove_selected_wallet(message: types.Message, state: FSMContext) -> None:
    data = await state.get_data()
    choices = data.get("wallet_choices")
    selected = choices.get(message.text) if isinstance(choices, dict) else None
    if not isinstance(selected, dict):
        await message.answer("Please select a wallet from the list.")
        return

    network = selected.get("network")
    address = selected.get("address")
    if not isinstance(network, str) or not isinstance(address, str):
        await state.clear()
        await message.answer("❌ Unable to remove wallet.", reply_markup=build_wallet_keyboard())
        return

    removed = await remove_wallet(message.from_user.id, network, address)
    await state.clear()
    if removed:
        await message.answer("✅ Wallet removed.", reply_markup=build_wallet_keyboard())
    else:
        await message.answer("❌ Wallet not found.", reply_markup=build_wallet_keyboard())


@router.message(
    lambda message: message.text == BACK_BUTTON,
    WalletStates.choosing_network,
)
@router.message(
    lambda message: message.text == BACK_BUTTON,
    WalletStates.entering_address,
)
@router.message(
    lambda message: message.text == BACK_BUTTON,
    WalletStates.selecting_wallet_to_remove,
)
async def cancel_wallet_action(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("👛 Wallets", reply_markup=build_wallet_keyboard())
