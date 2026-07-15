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
from app.utils.i18n import normalize_language, translate

router = Router()


class SettingsStates(StatesGroup):
    choosing_setting_type = State()
    choosing_language = State()
    choosing_currency = State()
    choosing_timezone = State()


async def _language(user_id: int) -> str:
    return normalize_language(await get_setting(user_id, "language"))


@router.message(lambda message: message.text in action_labels(7))
async def settings_entry(message: types.Message, state: FSMContext) -> None:
    await state.set_state(SettingsStates.choosing_setting_type)
    language = await _language(message.from_user.id)
    await message.answer(translate("settings.title", language), reply_markup=build_settings_keyboard(language))


@router.message(
    lambda message: message.text in {translate("settings.language", language) for language in ("English", "Ukrainian")}, SettingsStates.choosing_setting_type
)
async def choose_language(message: types.Message, state: FSMContext) -> None:
    await state.set_state(SettingsStates.choosing_language)
    language = await _language(message.from_user.id)
    await message.answer(translate("settings.choose_language", language), reply_markup=build_language_keyboard(language))


@router.message(
    lambda message: message.text in {"Ukrainian", "Українська", "English", "Англійська"},
    SettingsStates.choosing_language,
)
async def save_language(message: types.Message, state: FSMContext) -> None:
    selected = "Ukrainian" if message.text in {"Ukrainian", "Українська"} else "English"
    await upsert_setting(message.from_user.id, "language", selected)
    await state.clear()
    await message.answer(
        translate("settings.language_saved", selected),
        reply_markup=build_main_keyboard(selected),
    )


@router.message(
    lambda message: message.text in {translate("settings.currency", language) for language in ("English", "Ukrainian")}, SettingsStates.choosing_setting_type
)
async def choose_currency(message: types.Message, state: FSMContext) -> None:
    await state.set_state(SettingsStates.choosing_currency)
    language = await _language(message.from_user.id)
    await message.answer(translate("settings.choose_currency", language), reply_markup=build_currency_keyboard(language))


@router.message(
    lambda message: message.text in {"USD", "EUR", "UAH"},
    SettingsStates.choosing_currency,
)
async def save_currency(message: types.Message, state: FSMContext) -> None:
    await upsert_setting(message.from_user.id, "currency", message.text)
    await state.clear()
    language = await _language(message.from_user.id)
    await message.answer(translate("settings.updated", language), reply_markup=await user_main_keyboard(message.from_user.id))


@router.message(
    lambda message: message.text in {translate("settings.timezone", language) for language in ("English", "Ukrainian")}, SettingsStates.choosing_setting_type
)
async def choose_timezone(message: types.Message, state: FSMContext) -> None:
    await state.set_state(SettingsStates.choosing_timezone)
    language = await _language(message.from_user.id)
    await message.answer(
        translate("settings.choose_timezone", language),
        reply_markup=build_timezone_keyboard(language),
    )


@router.message(
    lambda message: message.text not in {translate("common.back", language) for language in ("English", "Ukrainian")},
    SettingsStates.choosing_timezone,
)
async def save_timezone(message: types.Message, state: FSMContext) -> None:
    timezone_name = (message.text or "").strip()
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        await message.answer(translate("settings.unknown_timezone", await _language(message.from_user.id)))
        return
    await upsert_setting(message.from_user.id, "timezone", timezone_name)
    await state.clear()
    language = await _language(message.from_user.id)
    await message.answer(translate("settings.updated", language), reply_markup=await user_main_keyboard(message.from_user.id))


@router.message(lambda message: message.text in {translate("common.back", language) for language in ("English", "Ukrainian")}, StateFilter(None))
@router.message(
    lambda message: message.text in {translate("common.back", language) for language in ("English", "Ukrainian")}, SettingsStates.choosing_setting_type
)
@router.message(
    lambda message: message.text in {translate("common.back", language) for language in ("English", "Ukrainian")}, SettingsStates.choosing_language
)
@router.message(
    lambda message: message.text in {translate("common.back", language) for language in ("English", "Ukrainian")}, SettingsStates.choosing_currency
)
@router.message(
    lambda message: message.text in {translate("common.back", language) for language in ("English", "Ukrainian")}, SettingsStates.choosing_timezone
)
async def back_to_main(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    language = await _language(message.from_user.id)
    await message.answer(translate("settings.returned", language), reply_markup=await user_main_keyboard(message.from_user.id))
