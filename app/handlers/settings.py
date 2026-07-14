from aiogram import Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.keyboards.main import action_labels, build_main_keyboard
from app.keyboards.settings import (
    build_currency_keyboard,
    build_language_keyboard,
    build_settings_keyboard,
    build_timezone_keyboard,
)
from app.services.settings_service import get_setting, upsert_setting
from app.handlers.common import user_main_keyboard

router = Router()


class SettingsStates(StatesGroup):
    choosing_setting_type = State()
    choosing_language = State()
    choosing_currency = State()
    choosing_timezone = State()


@router.message(lambda message: message.text in action_labels(7))
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
    lambda message: message.text in {"Ukrainian", "English", "Russian", "Chinese"},
    SettingsStates.choosing_language,
)
async def save_language(message: types.Message, state: FSMContext) -> None:
    await upsert_setting(message.from_user.id, "language", message.text)
    await state.clear()
    confirmations = {
        "Ukrainian": "✅ Мову змінено на українську.",
        "English": "✅ Language changed to English.",
        "Russian": "✅ Язык изменён на русский.",
        "Chinese": "✅ 语言已更改为中文。",
    }
    await message.answer(
        confirmations.get(message.text or "", "✅ Settings updated."),
        reply_markup=build_main_keyboard(message.text or "English"),
    )


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
    await message.answer("✅ Settings updated.", reply_markup=await user_main_keyboard(message.from_user.id))


@router.message(
    lambda message: message.text == "🕒 Timezone", SettingsStates.choosing_setting_type
)
async def choose_timezone(message: types.Message, state: FSMContext) -> None:
    await state.set_state(SettingsStates.choosing_timezone)
    await message.answer(
        "Choose a timezone or send any IANA name, for example Europe/Paris, "
        "America/Los_Angeles or Asia/Dubai:",
        reply_markup=build_timezone_keyboard(),
    )


@router.message(
    lambda message: message.text != "⬅ Back",
    SettingsStates.choosing_timezone,
)
async def save_timezone(message: types.Message, state: FSMContext) -> None:
    timezone_name = (message.text or "").strip()
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        await message.answer(
            "Unknown timezone. Use an IANA name such as Europe/Kyiv or Asia/Shanghai."
        )
        return
    await upsert_setting(message.from_user.id, "timezone", timezone_name)
    await state.clear()
    await message.answer("✅ Settings updated.", reply_markup=await user_main_keyboard(message.from_user.id))


@router.message(lambda message: message.text == "⬅ Back", StateFilter(None))
@router.message(
    lambda message: message.text == "⬅ Back", SettingsStates.choosing_setting_type
)
@router.message(
    lambda message: message.text == "⬅ Back", SettingsStates.choosing_language
)
@router.message(
    lambda message: message.text == "⬅ Back", SettingsStates.choosing_currency
)
@router.message(
    lambda message: message.text == "⬅ Back", SettingsStates.choosing_timezone
)
async def back_to_main(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("↩ Returned to main menu.", reply_markup=await user_main_keyboard(message.from_user.id))
