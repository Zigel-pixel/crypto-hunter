import logging

import aiosqlite
from aiogram import Router, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext

from app.handlers.common import user_main_keyboard
from app.keyboards.main import build_stopped_keyboard
from app.services.live_market_service import live_task_manager
from app.services.user_service import activate_user, stop_user

router = Router()
logger = logging.getLogger(__name__)


@router.message(CommandStart())
@router.message(lambda message: message.text == "▶️ Start")
async def cmd_start(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await live_task_manager.stop(message.chat.id)
    try:
        await activate_user(message.from_user.id)
    except aiosqlite.Error as exc:
        logger.exception("Could not activate user session: %s", exc)
        await message.answer("Session service is temporarily unavailable.")
        return
    await message.answer(
        "🏠 Crypto Hunter\n\nYour session is active.",
        reply_markup=await user_main_keyboard(message.from_user.id),
    )


@router.message(Command("restart"))
@router.message(lambda message: message.text == "🔄 Restart")
async def restart_session(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await live_task_manager.stop(message.chat.id)
    try:
        await activate_user(message.from_user.id)
    except aiosqlite.Error as exc:
        logger.exception("Could not restart user session: %s", exc)
        await message.answer("Session service is temporarily unavailable.")
        return
    await message.answer(
        "🔄 Your Crypto Hunter session has been restarted.",
        reply_markup=await user_main_keyboard(message.from_user.id),
    )


@router.message(Command("stop"))
@router.message(lambda message: message.text == "⏹ Stop")
async def stop_session(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await live_task_manager.stop(message.chat.id)
    try:
        await stop_user(message.from_user.id)
    except aiosqlite.Error as exc:
        logger.exception("Could not stop user session: %s", exc)
        await message.answer("Session service is temporarily unavailable.")
        return
    await message.answer(
        "⏹ Crypto Hunter is stopped for your account. "
        "Press ▶️ Start or send /start to continue.",
        reply_markup=build_stopped_keyboard(),
    )
