from aiogram import Router, types
from aiogram.filters import CommandStart

from app.keyboards.favorites import (
    build_coin_selection_keyboard,
    build_favorites_keyboard,
    build_remove_selection_keyboard,
)
from app.keyboards.main import build_main_keyboard
from app.services.favorites_service import add_favorite, get_favorites, remove_favorite

router = Router()

AVAILABLE_COINS = ["🟠 BTC", "🔵 ETH", "🟣 SOL"]
COIN_TITLES = {"🟠 BTC": "BTC", "🔵 ETH": "ETH", "🟣 SOL": "SOL"}


async def show_favorites_menu(message: types.Message) -> None:
    await message.answer(
        "⭐ Favorites",
        reply_markup=build_favorites_keyboard(),
    )


@router.message(lambda message: message.text == "⭐ Favorites")
async def favorites_entry(message: types.Message) -> None:
    await show_favorites_menu(message)


@router.message(lambda message: message.text == "➕ Add Coin")
async def add_coin_menu(message: types.Message) -> None:
    await message.answer(
        "➕ Choose a coin to add:",
        reply_markup=build_coin_selection_keyboard(AVAILABLE_COINS),
    )


@router.message(lambda message: message.text == "📋 My Favorites")
async def my_favorites(message: types.Message) -> None:
    favorites = await get_favorites(message.from_user.id)

    if favorites:
        text = "⭐ Your Favorites\n\n" + "\n".join(f"• {coin}" for coin in favorites)
    else:
        text = "⭐ You don't have favorite coins yet."

    await message.answer(text, reply_markup=build_favorites_keyboard())


@router.message(lambda message: message.text == "🗑 Remove Coin")
async def remove_coin_menu(message: types.Message) -> None:
    favorites = await get_favorites(message.from_user.id)

    if favorites:
        await message.answer(
            "🗑 Select a coin to remove:",
            reply_markup=build_remove_selection_keyboard(favorites),
        )
    else:
        await message.answer(
            "⭐ You don't have favorite coins yet.",
            reply_markup=build_favorites_keyboard(),
        )


@router.message(lambda message: message.text in AVAILABLE_COINS)
async def handle_add_coin(message: types.Message) -> None:
    coin_code = COIN_TITLES[message.text]
    await add_favorite(message.from_user.id, coin_code)
    await message.answer(
        f"✅ {coin_code} added to favorites.",
        reply_markup=build_favorites_keyboard(),
    )


@router.message(lambda message: message.text in {"BTC", "ETH", "SOL"})
async def handle_remove_coin(message: types.Message) -> None:
    await remove_favorite(message.from_user.id, message.text)
    await message.answer(
        f"🗑 {message.text} removed.",
        reply_markup=build_favorites_keyboard(),
    )


@router.message(lambda message: message.text == "⬅ Back")
async def back_to_main(message: types.Message) -> None:
    await message.answer(
        "↩ Returned to main menu.",
        reply_markup=build_main_keyboard(),
    )
