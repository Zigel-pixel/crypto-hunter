from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.keyboards.main import build_main_keyboard
from app.keyboards.portfolio import (
    build_portfolio_keyboard,
    build_portfolio_asset_keyboard,
    build_update_asset_keyboard,
)
from app.services.market_service import fetch_market_prices
from app.services.portfolio_service import (
    add_or_update_asset,
    build_portfolio_text,
    delete_asset,
    get_portfolio,
    update_asset_amount,
)

router = Router()


class PortfolioStates(StatesGroup):
    choosing_coin = State()
    entering_amount = State()
    selecting_update_asset = State()
    entering_updated_amount = State()
    selecting_remove_asset = State()


@router.message(lambda message: message.text == "💼 Portfolio")
async def portfolio_entry(message: types.Message) -> None:
    await message.answer("💼 Portfolio", reply_markup=build_portfolio_keyboard())


@router.message(lambda message: message.text == "➕ Add Asset")
async def add_asset_entry(message: types.Message, state: FSMContext) -> None:
    await state.set_state(PortfolioStates.choosing_coin)
    await message.answer(
        "Choose a coin:", reply_markup=build_portfolio_asset_keyboard()
    )


@router.message(
    lambda message: message.text in {"BTC", "ETH", "SOL"}, PortfolioStates.choosing_coin
)
async def choose_asset_coin(message: types.Message, state: FSMContext) -> None:
    await state.update_data(coin=message.text)
    await state.set_state(PortfolioStates.entering_amount)
    await message.answer("Enter amount:")


@router.message(PortfolioStates.entering_amount)
async def enter_asset_amount(message: types.Message, state: FSMContext) -> None:
    try:
        amount = float(message.text)
    except ValueError:
        await message.answer("Please enter a valid number.")
        return

    data = await state.get_data()
    coin = data.get("coin")
    if coin:
        await add_or_update_asset(message.from_user.id, coin, amount)
        await state.clear()
        await message.answer("✅ Asset saved.", reply_markup=build_portfolio_keyboard())


@router.message(lambda message: message.text == "📋 My Portfolio")
async def my_portfolio(message: types.Message) -> None:
    _, prices = await fetch_market_prices()
    if not prices:
        await message.answer(
            "❌ Failed to fetch market data.", reply_markup=build_portfolio_keyboard()
        )
        return

    text = await build_portfolio_text(message.from_user.id, prices)
    await message.answer(text, reply_markup=build_portfolio_keyboard())


@router.message(lambda message: message.text == "✏ Update Asset")
async def update_asset_entry(message: types.Message, state: FSMContext) -> None:
    assets = await get_portfolio(message.from_user.id)
    if not assets:
        await message.answer(
            "No assets in your portfolio.", reply_markup=build_portfolio_keyboard()
        )
        return

    await state.set_state(PortfolioStates.selecting_update_asset)
    await message.answer(
        "Select an asset to update:",
        reply_markup=build_update_asset_keyboard([asset["coin"] for asset in assets]),
    )


@router.message(
    lambda message: message.text in {"BTC", "ETH", "SOL"},
    PortfolioStates.selecting_update_asset,
)
async def select_asset_to_update(message: types.Message, state: FSMContext) -> None:
    await state.update_data(coin=message.text)
    await state.set_state(PortfolioStates.entering_updated_amount)
    await message.answer("Enter new amount:")


@router.message(PortfolioStates.entering_updated_amount)
async def enter_updated_amount(message: types.Message, state: FSMContext) -> None:
    try:
        amount = float(message.text)
    except ValueError:
        await message.answer("Please enter a valid number.")
        return

    data = await state.get_data()
    coin = data.get("coin")
    if coin:
        await update_asset_amount(message.from_user.id, coin, amount)
        await state.clear()
        await message.answer(
            "✅ Asset updated.", reply_markup=build_portfolio_keyboard()
        )


@router.message(lambda message: message.text == "🗑 Remove Asset")
async def remove_asset_entry(message: types.Message, state: FSMContext) -> None:
    assets = await get_portfolio(message.from_user.id)
    if not assets:
        await message.answer(
            "No assets in your portfolio.", reply_markup=build_portfolio_keyboard()
        )
        return

    await state.set_state(PortfolioStates.selecting_remove_asset)
    await message.answer(
        "Select an asset to remove:",
        reply_markup=build_update_asset_keyboard([asset["coin"] for asset in assets]),
    )


@router.message(
    lambda message: message.text in {"BTC", "ETH", "SOL"},
    PortfolioStates.selecting_remove_asset,
)
async def remove_selected_asset(message: types.Message, state: FSMContext) -> None:
    removed = await delete_asset(message.from_user.id, message.text)
    await state.clear()
    if removed:
        await message.answer(
            "✅ Asset removed.", reply_markup=build_portfolio_keyboard()
        )
    else:
        await message.answer(
            "❌ Asset not found.", reply_markup=build_portfolio_keyboard()
        )


@router.message(lambda message: message.text == "⬅ Back")
async def back_to_main(message: types.Message) -> None:
    await message.answer("↩ Returned to main menu.", reply_markup=build_main_keyboard())
