from aiogram import F, Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.keyboards.alerts import (
    build_alert_condition_keyboard,
    build_alerts_keyboard,
    build_coin_selection_keyboard,
    build_delete_alert_keyboard,
    build_delete_confirmation_keyboard,
    alert_action_labels,
)
from app.keyboards.main import action_labels, build_main_keyboard
from app.services.alerts_service import create_alert, delete_alert, get_alert, get_alerts
from app.services.alert_formatter import format_alert
from app.services.settings_service import get_setting
from app.handlers.message_updates import safe_update_message
from app.handlers.common import user_main_keyboard

router = Router()


class AlertStates(StatesGroup):
    waiting_for_coin = State()
    waiting_for_condition = State()
    waiting_for_price = State()
    deleting_alert = State()


@router.message(lambda message: message.text in action_labels(2))
async def alerts_entry(message: types.Message) -> None:
    language = await get_setting(message.from_user.id, "language") or "English"
    await message.answer("🔔 Сповіщення" if language == "Ukrainian" else "🔔 Alerts", reply_markup=build_alerts_keyboard(language))


@router.message(lambda message: message.text in alert_action_labels("alert.create"))
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
            reply_markup=await user_main_keyboard(message.from_user.id),
        )
    else:
        await state.clear()
        await message.answer(
            "❌ Unable to create alert.", reply_markup=await user_main_keyboard(message.from_user.id)
        )


@router.message(lambda message: message.text in alert_action_labels("alert.list"))
async def my_alerts(message: types.Message) -> None:
    language = await get_setting(message.from_user.id, "language") or "English"
    alerts = await get_alerts(message.from_user.id)
    if not alerts:
        await message.answer("Активних сповіщень немає." if language == "Ukrainian" else "No active alerts.", reply_markup=build_alerts_keyboard(language))
        return

    lines = [
        f"{item['coin']} {item['condition']} {item['target_price']}" for item in alerts
    ]
    await message.answer("\n".join(format_alert(item, language) for item in alerts), reply_markup=build_alerts_keyboard(language))


@router.message(lambda message: message.text in alert_action_labels("alert.delete"))
async def delete_alert_entry(message: types.Message, state: FSMContext) -> None:
    language = await get_setting(message.from_user.id, "language") or "English"
    alerts = await get_alerts(message.from_user.id)
    if not alerts:
        await message.answer("Активних сповіщень немає." if language == "Ukrainian" else "No active alerts.", reply_markup=build_alerts_keyboard(language))
        return

    await state.clear()
    await message.answer(
        "Оберіть сповіщення для видалення:" if language == "Ukrainian" else "Select an alert to delete:",
        reply_markup=build_delete_alert_keyboard(alerts, language),
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


@router.callback_query(F.data.startswith("alert:delete:"))
async def handle_delete_callback(callback: types.CallbackQuery) -> None:
    await callback.answer()
    language = await get_setting(callback.from_user.id, "language") or "English"
    data = callback.data or ""
    if callback.message is None:
        return
    if data == "alert:delete:back":
        alerts = await get_alerts(callback.from_user.id)
        text = "Оберіть сповіщення для видалення:" if language == "Ukrainian" else "Select an alert to delete:"
        await safe_update_message(callback.message, text, build_delete_alert_keyboard(alerts, language))
        return
    try:
        alert_id = int(data.rsplit(":", 1)[1])
    except ValueError:
        return
    alert = await get_alert(alert_id, callback.from_user.id)
    if data.startswith("alert:delete:select:"):
        if alert is None:
            await safe_update_message(callback.message, "Сповіщення вже видалено." if language == "Ukrainian" else "Alert already deleted.", None)
            return
        heading = "Підтвердити видалення?" if language == "Ukrainian" else "Confirm deletion?"
        await safe_update_message(callback.message, f"{heading}\n\n{format_alert(alert, language)}", build_delete_confirmation_keyboard(alert_id, language))
        return
    deleted = await delete_alert(alert_id, callback.from_user.id)
    text = ("✅ Сповіщення видалено." if language == "Ukrainian" else "✅ Alert deleted.") if deleted else ("ℹ️ Сповіщення вже видалено." if language == "Ukrainian" else "ℹ️ Alert was already deleted.")
    await safe_update_message(callback.message, text, None)


@router.message(lambda message: message.text == "⬅ Back", StateFilter(None))
@router.message(
    lambda message: message.text == "⬅ Back", AlertStates.waiting_for_coin
)
@router.message(
    lambda message: message.text == "⬅ Back", AlertStates.waiting_for_condition
)
@router.message(
    lambda message: message.text == "⬅ Back", AlertStates.waiting_for_price
)
@router.message(
    lambda message: message.text == "⬅ Back", AlertStates.deleting_alert
)
async def back_to_main(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("↩ Returned to main menu.", reply_markup=await user_main_keyboard(message.from_user.id))
