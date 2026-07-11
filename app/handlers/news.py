from aiogram import Router, types

from app.keyboards.main import build_main_keyboard

router = Router()


@router.message(lambda message: message.text == "📰 News")
async def news_entry(message: types.Message) -> None:
    await message.answer(
        "📰 News\n\nNews service is ready for future expansion.",
        reply_markup=build_main_keyboard(),
    )
