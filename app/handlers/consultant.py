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
)
from app.keyboards.main import action_labels, build_main_keyboard
from app.services.consultant_service import build_market_analysis, build_wallet_analysis

router = Router()


class ConsultantStates(StatesGroup):
    entering_question = State()


@router.message(lambda message: message.text in action_labels(6))
async def consultant_entry(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "🤖 AI-консультант\n\nАналізую актуальні курси, новини та ваші гаманці.",
        reply_markup=build_consultant_keyboard(),
    )


@router.message(lambda message: message.text == MARKET_ANALYSIS_BUTTON)
async def market_analysis(message: types.Message) -> None:
    await message.answer(
        await build_market_analysis(), reply_markup=build_consultant_keyboard()
    )


@router.message(lambda message: message.text == WALLET_ANALYSIS_BUTTON)
async def wallet_analysis(message: types.Message) -> None:
    await message.answer(
        await build_wallet_analysis(message.from_user.id),
        reply_markup=build_consultant_keyboard(),
    )


@router.message(lambda message: message.text == ASK_CONSULTANT_BUTTON)
async def ask_consultant(message: types.Message, state: FSMContext) -> None:
    await state.set_state(ConsultantStates.entering_question)
    await message.answer(
        "Напишіть питання про BTC, ETH, SOL або BNB. Наприклад: «Чи варто зараз купувати BTC?»",
        reply_markup=build_consultant_keyboard(),
    )


@router.message(
    lambda message: message.text != BACK_BUTTON,
    ConsultantStates.entering_question,
)
async def answer_question(message: types.Message, state: FSMContext) -> None:
    question = (message.text or "").strip()
    if len(question) < 3:
        await message.answer("Напишіть трохи детальніше питання.")
        return
    await state.clear()
    await message.answer(
        await build_market_analysis(question),
        reply_markup=build_consultant_keyboard(),
    )


@router.message(lambda message: message.text == BACK_BUTTON, StateFilter(None))
@router.message(lambda message: message.text == BACK_BUTTON, ConsultantStates.entering_question)
async def back_to_main(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("↩ Головне меню.", reply_markup=build_main_keyboard())
