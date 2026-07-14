from __future__ import annotations

import logging

from aiogram import types
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import BufferedInputFile, InlineKeyboardMarkup, InputMediaPhoto

logger = logging.getLogger(__name__)


async def safe_update_message(
    message: types.Message,
    text: str,
    reply_markup: InlineKeyboardMarkup | None,
) -> None:
    try:
        if message.text is not None:
            await message.edit_text(text, reply_markup=reply_markup)
        elif message.caption is not None:
            await message.edit_caption(caption=text, reply_markup=reply_markup)
        else:
            await message.answer(text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc).lower():
            logger.debug("Telegram message already contains requested content")
            return
        logger.warning("Could not update Telegram message; sending a new one: %s", exc)
        await message.answer(text, reply_markup=reply_markup)


async def safe_update_photo(
    message: types.Message,
    photo: BufferedInputFile,
    caption: str,
    reply_markup: InlineKeyboardMarkup,
) -> types.Message | None:
    try:
        if message.photo:
            result = await message.edit_media(
                InputMediaPhoto(media=photo, caption=caption), reply_markup=reply_markup
            )
            return result if isinstance(result, types.Message) else message
        else:
            return await message.answer_photo(photo, caption=caption, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc).lower():
            return message
        logger.warning("Could not update Telegram media; sending a new one: %s", exc)
        return await message.answer_photo(photo, caption=caption, reply_markup=reply_markup)
