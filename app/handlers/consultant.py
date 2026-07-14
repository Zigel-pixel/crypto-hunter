from aiogram import Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.keyboards.consultant import (
    ASK_CONSULTANT_BUTTON,
    BACK_BUTTON,
    CONSULTANT_BUTTON,
    MARKET_ANALYSIS_BUTTON,
    WALLET_ANALYSIS_BUTTON,
    build_consultant_keyboard,
    consultant_labels,
)
from app.keyboards.main import action_labels, build_main_keyboard
from app.services.consultant_service import answer_consultant_question, build_market_analysis, build_wallet_analysis
from app.services.settings_service import get_setting, upsert_setting
from app.handlers.common import user_main_keyboard

router = Router(name="consultant")
question_router = Router(name="consultant_question")


class ConsultantStates(StatesGroup):
    entering_question = State()


@router.message(lambda message: message.text in action_labels(6))
async def consultant_entry(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    language = await get_setting(message.from_user.id, "language") or "English"
    notice_seen = await get_setting(message.from_user.id, "ai_notice_seen")
    notice = ""
    if notice_seen != "1":
        notice = ("\n\nℹ️ Аналіз може помилятися; перевіряйте важливі рішення самостійно." if language == "Ukrainian" else "\n\nℹ️ Analysis can be wrong; independently verify important decisions.")
        await upsert_setting(message.from_user.id, "ai_notice_seen", "1")
    await message.answer(
        (("🤖 AI-консультант\n\nВідповідаю за темою питання, використовуючи доступні ринкові дані." if language == "Ukrainian" else "🤖 AI Consultant\n\nI answer the actual topic using available market data.") + notice),
        reply_markup=build_consultant_keyboard(language),
    )


@router.message(lambda message: message.text in consultant_labels("market"))
async def market_analysis(message: types.Message) -> None:
    language = await get_setting(message.from_user.id, "language") or "English"
    await message.answer(
        await build_market_analysis(language=language), reply_markup=build_consultant_keyboard(language)
    )


@router.message(lambda message: message.text in consultant_labels("wallet"))
async def wallet_analysis(message: types.Message) -> None:
    language = await get_setting(message.from_user.id, "language") or "English"
    await message.answer(
        await build_wallet_analysis(message.from_user.id),
        reply_markup=build_consultant_keyboard(language),
    )


@router.message(lambda message: message.text in consultant_labels("ask"))
async def ask_consultant(message: types.Message, state: FSMContext) -> None:
    language = await get_setting(message.from_user.id, "language") or "English"
    await state.set_state(ConsultantStates.entering_question)
    await message.answer(
        "Напишіть питання про актив, стейблкоїни, DeFi, ризик або ринок." if language == "Ukrainian" else "Ask about an asset, stablecoins, DeFi, risk, or the market.",
        reply_markup=build_consultant_keyboard(language),
    )


@question_router.message(
    lambda message: message.text != BACK_BUTTON,
    ConsultantStates.entering_question,
)
async def answer_question(message: types.Message, state: FSMContext) -> None:
    question = (message.text or "").strip()
    language = await get_setting(message.from_user.id, "language") or "English"
    if len(question) < 3:
        await message.answer("Напишіть трохи детальніше питання." if language == "Ukrainian" else "Please provide a little more detail.")
        return
    await state.clear()
    await message.answer(
        await answer_consultant_question(question, language),
        reply_markup=build_consultant_keyboard(language),
    )


@router.message(lambda message: message.text == BACK_BUTTON, StateFilter(None))
@router.message(lambda message: message.text == BACK_BUTTON, ConsultantStates.entering_question)
async def back_to_main(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    language = await get_setting(message.from_user.id, "language") or "English"
    await message.answer("↩ Головне меню." if language == "Ukrainian" else "↩ Main menu.", reply_markup=await user_main_keyboard(message.from_user.id))
