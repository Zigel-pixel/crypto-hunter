from aiogram import Router, types
from aiogram.enums import ParseMode
from aiogram.filters import StateFilter
from aiogram.filters import Command

from app.keyboards.main import action_labels, build_main_keyboard
from app.keyboards.news import BACK_BUTTON, REFRESH_NEWS_BUTTON, build_news_keyboard
from app.services.news_service import build_news_text, get_news

router = Router()


@router.message(Command("news"))
@router.message(lambda message: message.text in action_labels(3))
async def news_entry(message: types.Message) -> None:
    await _send_news(message)


@router.message(lambda message: message.text == REFRESH_NEWS_BUTTON)
async def refresh_news(message: types.Message) -> None:
    await _send_news(message)


@router.message(lambda message: message.text == BACK_BUTTON, StateFilter(None))
async def back_to_main(message: types.Message) -> None:
    await message.answer("↩ Головне меню.", reply_markup=build_main_keyboard())


async def _send_news(message: types.Message) -> None:
    items = await get_news()
    await message.answer(
        build_news_text(items),
        parse_mode=ParseMode.HTML,
        link_preview_options=types.LinkPreviewOptions(is_disabled=True),
        reply_markup=build_news_keyboard(),
    )
