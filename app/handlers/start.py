from aiogram import Router, types
from aiogram.filters import CommandStart

from app.handlers.common import user_main_keyboard

router = Router()


@router.message(CommandStart())
async def cmd_start(message: types.Message) -> None:
    await message.answer(
        "🏠 Crypto Hunter\n\nWelcome to the MVP bot.",
        reply_markup=await user_main_keyboard(message.from_user.id),
    )
