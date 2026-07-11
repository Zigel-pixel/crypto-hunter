from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.keyboards.main import build_main_keyboard
from app.keyboards.settings import (
    build_currency_keyboard,
    build_language_keyboard,
    build_settings_keyboard,
    build_timezone_keyboard,
)
from app.services.settings_service import get_setting, upsert_setting

router = Router()


class SettingsStates(StatesGroup):
    choosing_setting_type = State()
    choosing_language = State()
    choosing_currency = State()
    choosing_timezone = State()


@router.message(lambda message: message.text == "⚙ Settings")
async def settings_entry(message: types.Message, state: FSMContext) -> None:
    await state.set_state(SettingsStates.choosing_setting_type)
    await message.answer("⚙ Settings", reply_markup=build_settings_keyboard())


@router.message(
    lambda message: message.text == "🌐 Language", SettingsStates.choosing_setting_type
)
async def choose_language(message: types.Message, state: FSMContext) -> None:
    await state.set_state(SettingsStates.choosing_language)
    await message.answer("Choose language:", reply_markup=build_language_keyboard())


@router.message(
    lambda message: message.text in {"Ukrainian", "English"},
    SettingsStates.choosing_language,
)
async def save_language(message: types.Message, state: FSMContext) -> None:
    await upsert_setting(message.from_user.id, "language", message.text)
    await state.clear()
    await message.answer("✅ Settings updated.", reply_markup=build_main_keyboard())


@router.message(
    lambda message: message.text == "💱 Currency", SettingsStates.choosing_setting_type
)
async def choose_currency(message: types.Message, state: FSMContext) -> None:
    await state.set_state(SettingsStates.choosing_currency)
    await message.answer("Choose currency:", reply_markup=build_currency_keyboard())


@router.message(
    lambda message: message.text in {"USD", "EUR", "UAH"},
    SettingsStates.choosing_currency,
)
async def save_currency(message: types.Message, state: FSMContext) -> None:
    await upsert_setting(message.from_user.id, "currency", message.text)
    await state.clear()
    await message.answer("✅ Settings updated.", reply_markup=build_main_keyboard())


@router.message(
    lambda message: message.text == "🕒 Timezone", SettingsStates.choosing_setting_type
)
async def choose_timezone(message: types.Message, state: FSMContext) -> None:
    await state.set_state(SettingsStates.choosing_timezone)
    await message.answer("Choose timezone:", reply_markup=build_timezone_keyboard())


@router.message(
    lambda message: message.text in {"UTC", "UTC+2", "UTC+3"},
    SettingsStates.choosing_timezone,
)
async def save_timezone(message: types.Message, state: FSMContext) -> None:
    await upsert_setting(message.from_user.id, "timezone", message.text)
    await state.clear()
    await message.answer("✅ Settings updated.", reply_markup=build_main_keyboard())


@router.message(lambda message: message.text == "⬅ Back")
async def back_to_main(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("↩ Returned to main menu.", reply_markup=build_main_keyboard())
