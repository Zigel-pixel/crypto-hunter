from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from app.keyboards.main import build_main_keyboard
from app.services.market_service import (
    fetch_market_prices,
    format_market_cap,
    format_percent,
    format_price,
)

router = Router()


def build_rates_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔄 Refresh")],
            [KeyboardButton(text="⬅ Back")],
        ],
        resize_keyboard=True,
    )


async def send_rates(message: types.Message) -> None:
    updated_at, prices = await fetch_market_prices()

    if not updated_at or not prices:
        await message.answer("❌ Failed to fetch market data. Please try again later.")
        return

    lines = [
        "📈 Current Market",
        "",
        "🟠 Bitcoin",
        f"💵 Price:\n{format_price(prices['BTC']['price'])}",
        f"📊 24h:\n{format_percent(prices['BTC']['change_24h'])}",
        f"💰 Market Cap:\n{format_market_cap(prices['BTC']['market_cap'])}",
        f"💵 Volume 24h:\n{format_market_cap(prices['BTC']['volume_24h'])}",
        "",
        "-------------------------",
        "",
        "🔵 Ethereum",
        f"💵 Price:\n{format_price(prices['ETH']['price'])}",
        f"📊 24h:\n{format_percent(prices['ETH']['change_24h'])}",
        f"💰 Market Cap:\n{format_market_cap(prices['ETH']['market_cap'])}",
        f"💵 Volume 24h:\n{format_market_cap(prices['ETH']['volume_24h'])}",
        "",
        "-------------------------",
        "",
        "🟣 Solana",
        f"💵 Price:\n{format_price(prices['SOL']['price'])}",
        f"📊 24h:\n{format_percent(prices['SOL']['change_24h'])}",
        f"💰 Market Cap:\n{format_market_cap(prices['SOL']['market_cap'])}",
        f"💵 Volume 24h:\n{format_market_cap(prices['SOL']['volume_24h'])}",
        "",
        f"🕒 Updated:\n{updated_at}",
    ]

    await message.answer("\n".join(lines), reply_markup=build_rates_keyboard())


@router.message(Command("rates"))
async def show_rates(message: types.Message) -> None:
    await send_rates(message)


@router.message(lambda message: message.text == "📈 Rates")
async def show_rates_button(message: types.Message) -> None:
    await send_rates(message)


@router.message(lambda message: message.text == "🔄 Refresh")
async def refresh_rates(message: types.Message) -> None:
    await send_rates(message)


@router.message(lambda message: message.text == "⬅ Back")
async def back_to_main(message: types.Message) -> None:
    await message.answer("↩ Returned to main menu.", reply_markup=build_main_keyboard())
