from aiogram import Router, types
from aiogram.enums import ParseMode
from aiogram.filters import StateFilter
from aiogram.filters import Command

from app.keyboards.main import action_labels, build_main_keyboard
from app.keyboards.news import build_news_keyboard, news_action_labels
from app.services.news_service import build_news_text, get_news
from app.services.settings_service import get_setting

router = Router()


@router.message(Command("news"))
@router.message(lambda message: message.text in action_labels(3))
async def news_entry(message: types.Message) -> None:
    await _send_news(message)


@router.message(lambda message: message.text in news_action_labels("news.refresh"))
async def refresh_news(message: types.Message) -> None:
    await _send_news(message)


@router.message(lambda message: message.text in news_action_labels("common.back"), StateFilter(None))
async def back_to_main(message: types.Message) -> None:
    await message.answer("↩ Головне меню.", reply_markup=build_main_keyboard())


async def _send_news(message: types.Message) -> None:
    language = await get_setting(message.from_user.id, "language") or "English"
    items = await get_news()
    await message.answer(
        build_news_text(items, language),
        parse_mode=ParseMode.HTML,
        link_preview_options=types.LinkPreviewOptions(is_disabled=True),
        reply_markup=build_news_keyboard(language),
    )
