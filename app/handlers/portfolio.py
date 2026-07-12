from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile

from app.keyboards.main import action_labels, build_main_keyboard
from app.keyboards.portfolio import (
    build_portfolio_keyboard,
    build_portfolio_asset_keyboard,
    build_update_asset_keyboard,
)
from app.services.portfolio_service import (
    add_or_update_asset,
    delete_asset,
    get_portfolio,
    get_portfolio_text,
    get_portfolio_chart,
)
from app.utils.assets import SUPPORTED_SYMBOLS

router = Router()


class PortfolioStates(StatesGroup):
    choosing_coin = State()
    entering_amount = State()
    entering_buy_price = State()
    selecting_update_asset = State()
    entering_updated_amount = State()
    entering_updated_price = State()
    selecting_remove_asset = State()


@router.message(lambda message: message.text in action_labels(4))
async def portfolio_entry(message: types.Message) -> None:
    await message.answer("💼 Portfolio", reply_markup=build_portfolio_keyboard())


@router.message(lambda message: message.text == "➕ Add Asset")
async def add_asset_entry(message: types.Message, state: FSMContext) -> None:
    await state.set_state(PortfolioStates.choosing_coin)
    await message.answer(
        "Choose a coin:", reply_markup=build_portfolio_asset_keyboard()
    )


@router.message(
    lambda message: message.text in SUPPORTED_SYMBOLS, PortfolioStates.choosing_coin
)
async def choose_asset_coin(message: types.Message, state: FSMContext) -> None:
    await state.update_data(coin=message.text)
    await state.set_state(PortfolioStates.entering_amount)
    await message.answer("Enter amount:")


@router.message(PortfolioStates.entering_amount)
async def enter_asset_amount(message: types.Message, state: FSMContext) -> None:
    try:
        amount = float(message.text or "")
    except (TypeError, ValueError):
        await message.answer("Please enter a valid number.")
        return
    if amount <= 0:
        await message.answer("Amount must be greater than zero.")
        return
    await state.update_data(amount=amount)
    await state.set_state(PortfolioStates.entering_buy_price)
    await message.answer("Enter your average purchase price in USD:")


@router.message(PortfolioStates.entering_buy_price)
async def enter_buy_price(message: types.Message, state: FSMContext) -> None:
    try:
        buy_price = float(message.text or "")
    except (TypeError, ValueError):
        await message.answer("Please enter a valid price.")
        return
    if buy_price <= 0:
        await message.answer("Price must be greater than zero.")
        return
    data = await state.get_data()
    coin = data.get("coin")
    amount = data.get("amount")
    if isinstance(coin, str) and isinstance(amount, float):
        await add_or_update_asset(message.from_user.id, coin, amount, buy_price)
    await state.clear()
    await message.answer("✅ Asset saved.", reply_markup=build_portfolio_keyboard())


@router.message(lambda message: message.text == "📋 My Portfolio")
async def my_portfolio(message: types.Message) -> None:
    text = await get_portfolio_text(message.from_user.id)
    if text is None:
        await message.answer(
            "❌ Failed to fetch market data.", reply_markup=build_portfolio_keyboard()
        )
        return

    await message.answer(text, reply_markup=build_portfolio_keyboard())


@router.message(lambda message: message.text == "📊 P/L Chart")
async def portfolio_chart(message: types.Message) -> None:
    chart = await get_portfolio_chart(message.from_user.id)
    if chart is None:
        await message.answer(
            "Add assets with an average purchase price to build a P/L chart.",
            reply_markup=build_portfolio_keyboard(),
        )
        return
    await message.answer_photo(
        BufferedInputFile(chart, filename="portfolio-pl.png"),
        caption="📊 Portfolio profit / loss by asset",
        reply_markup=build_portfolio_keyboard(),
    )


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
    lambda message: message.text in SUPPORTED_SYMBOLS,
    PortfolioStates.selecting_update_asset,
)
async def select_asset_to_update(message: types.Message, state: FSMContext) -> None:
    await state.update_data(coin=message.text)
    await state.set_state(PortfolioStates.entering_updated_amount)
    await message.answer("Enter new amount:")


@router.message(PortfolioStates.entering_updated_amount)
async def enter_updated_amount(message: types.Message, state: FSMContext) -> None:
    try:
        amount = float(message.text or "")
    except (TypeError, ValueError):
        await message.answer("Please enter a valid number.")
        return
    if amount <= 0:
        await message.answer("Amount must be greater than zero.")
        return
    await state.update_data(amount=amount)
    await state.set_state(PortfolioStates.entering_updated_price)
    await message.answer("Enter new average purchase price in USD:")


@router.message(PortfolioStates.entering_updated_price)
async def enter_updated_price(message: types.Message, state: FSMContext) -> None:
    try:
        price = float(message.text or "")
    except (TypeError, ValueError):
        await message.answer("Please enter a valid price.")
        return
    if price <= 0:
        await message.answer("Price must be greater than zero.")
        return
    data = await state.get_data()
    coin = data.get("coin")
    amount = data.get("amount")
    if isinstance(coin, str) and isinstance(amount, float):
        await add_or_update_asset(message.from_user.id, coin, amount, price)
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
    lambda message: message.text in SUPPORTED_SYMBOLS,
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


@router.message(lambda message: message.text == "⬅ Back", StateFilter(None))
@router.message(
    lambda message: message.text == "⬅ Back", PortfolioStates.choosing_coin
)
@router.message(
    lambda message: message.text == "⬅ Back", PortfolioStates.entering_amount
)
@router.message(
    lambda message: message.text == "⬅ Back", PortfolioStates.entering_buy_price
)
@router.message(
    lambda message: message.text == "⬅ Back", PortfolioStates.selecting_update_asset
)
@router.message(
    lambda message: message.text == "⬅ Back", PortfolioStates.entering_updated_amount
)
@router.message(
    lambda message: message.text == "⬅ Back", PortfolioStates.entering_updated_price
)
@router.message(
    lambda message: message.text == "⬅ Back", PortfolioStates.selecting_remove_asset
)
async def back_to_main(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("↩ Returned to main menu.", reply_markup=build_main_keyboard())
