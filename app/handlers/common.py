from aiogram.types import ReplyKeyboardMarkup

from app.keyboards.main import build_main_keyboard
from app.services.settings_service import get_setting


async def user_main_keyboard(telegram_id: int) -> ReplyKeyboardMarkup:
    language = await get_setting(telegram_id, "language") or "English"
    return build_main_keyboard(language)
