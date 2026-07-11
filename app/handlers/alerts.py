from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.keyboards.alerts import (
    build_alert_condition_keyboard,
    build_alerts_keyboard,
    build_coin_selection_keyboard,
    build_delete_alert_keyboard,
)
from app.keyboards.main import build_main_keyboard
from app.services.alerts_service import create_alert, delete_alert, get_alerts

router = Router()


class AlertStates(StatesGroup):
    waiting_for_coin = State()
    waiting_for_condition = State()
    waiting_for_price = State()
    deleting_alert = State()


@router.message(Command("start"))
async def handle_start(message: types.Message) -> None:
    await message.answer("Welcome to Crypto Hunter", reply_markup=build_main_keyboard())


@router.message(lambda message: message.text == "🔔 Alerts")
async def alerts_entry(message: types.Message) -> None:
    await message.answer("🔔 Alerts", reply_markup=build_alerts_keyboard())


@router.message(lambda message: message.text == "➕ Create Alert")
async def create_alert_entry(message: types.Message, state: FSMContext) -> None:
    await state.set_state(AlertStates.waiting_for_coin)
    await message.answer("Choose coin", reply_markup=build_coin_selection_keyboard())


@router.message(
    lambda message: message.text in {"BTC", "ETH", "SOL"}, AlertStates.waiting_for_coin
)
async def choose_coin(message: types.Message, state: FSMContext) -> None:
    await state.update_data(coin=message.text)
    await state.set_state(AlertStates.waiting_for_condition)
    await message.answer(
        "Choose condition", reply_markup=build_alert_condition_keyboard()
    )


@router.message(
    lambda message: message.text in {">", "<"}, AlertStates.waiting_for_condition
)
async def choose_condition(message: types.Message, state: FSMContext) -> None:
    await state.update_data(condition=message.text)
    await state.set_state(AlertStates.waiting_for_price)
    await message.answer("Enter target price\nExample:\n70000")


@router.message(AlertStates.waiting_for_price)
async def enter_target_price(message: types.Message, state: FSMContext) -> None:
    try:
        target_price = float(message.text)
    except ValueError:
        await message.answer("Please enter a valid number.")
        return

    data = await state.get_data()
    coin = data.get("coin")
    condition = data.get("condition")

    if coin and condition:
        await create_alert(message.from_user.id, coin, condition, target_price)
        await state.clear()
        await message.answer(
            f"✅ Alert created\n{coin} {condition} {target_price}",
            reply_markup=build_main_keyboard(),
        )
    else:
        await state.clear()
        await message.answer(
            "❌ Unable to create alert.", reply_markup=build_main_keyboard()
        )


@router.message(lambda message: message.text == "📋 My Alerts")
async def my_alerts(message: types.Message) -> None:
    alerts = await get_alerts(message.from_user.id)
    if not alerts:
        await message.answer("No active alerts.", reply_markup=build_alerts_keyboard())
        return

    lines = [
        f"{item['coin']} {item['condition']} {item['target_price']}" for item in alerts
    ]
    await message.answer("\n".join(lines), reply_markup=build_alerts_keyboard())


@router.message(lambda message: message.text == "🗑 Delete Alert")
async def delete_alert_entry(message: types.Message, state: FSMContext) -> None:
    alerts = await get_alerts(message.from_user.id)
    if not alerts:
        await message.answer("No active alerts.", reply_markup=build_alerts_keyboard())
        return

    await state.set_state(AlertStates.deleting_alert)
    await message.answer(
        "Select an alert to delete:",
        reply_markup=build_delete_alert_keyboard(alerts),
    )


@router.message(AlertStates.deleting_alert)
async def delete_selected_alert(message: types.Message, state: FSMContext) -> None:
    try:
        alert_id = int(message.text)
    except ValueError:
        await message.answer("Please select a valid alert number.")
        return

    deleted = await delete_alert(alert_id, message.from_user.id)
    await state.clear()

    if deleted:
        await message.answer("✅ Alert deleted.", reply_markup=build_alerts_keyboard())
    else:
        await message.answer(
            "❌ Alert not found.", reply_markup=build_alerts_keyboard()
        )


@router.message(lambda message: message.text == "⬅ Back")
async def back_to_main(message: types.Message) -> None:
    await message.answer("↩ Returned to main menu.", reply_markup=build_main_keyboard())
