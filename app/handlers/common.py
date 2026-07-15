from aiogram.types import ReplyKeyboardMarkup

from app.keyboards.main import build_main_keyboard
from app.services.settings_service import resolve_user_language


async def user_main_keyboard(telegram_id: int) -> ReplyKeyboardMarkup:
    language = await resolve_user_language(telegram_id)
    return build_main_keyboard(language)
