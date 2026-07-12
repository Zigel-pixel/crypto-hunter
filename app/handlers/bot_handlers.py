from aiogram import Router, types
from aiogram.filters import Command

from app.keyboards.main import build_main_keyboard
from app.services.market_service import fetch_market_prices

router = Router()


@router.message(Command("rates"))
async def show_rates(message: types.Message) -> None:
    updated_at, prices = await fetch_market_prices()

    if not updated_at or not prices:
        await message.answer("❌ Failed to fetch market data. Please try again later.")
        return

    lines = [
        "📈 Current Market",
        "",
        f"🟠 BTC: ${prices['BTC']:.2f}",
        f"🔵 ETH: ${prices['ETH']:.2f}",
        f"🟣 SOL: ${prices['SOL']:.2f}",
        "",
        f"🕒 Updated: {updated_at}",
    ]

    await message.answer("\n".join(lines))


@router.message(lambda message: message.text == "📈 Rates")
async def show_rates_button(message: types.Message) -> None:
    await show_rates(message)


@router.message(lambda message: message.text == "🔔 Alerts")
async def show_alerts(message: types.Message) -> None:
    await message.answer(
        "🚧 Alerts are coming soon.",
        reply_markup=build_main_keyboard(),
    )


@router.message(lambda message: message.text == "📰 News")
async def show_news(message: types.Message) -> None:
    await message.answer(
        "🚧 News are coming soon.",
        reply_markup=build_main_keyboard(),
    )


@router.message(lambda message: message.text == "⚙️ Settings")
async def show_settings(message: types.Message) -> None:
    await message.answer(
        "🚧 Settings are coming soon.",
        reply_markup=build_main_keyboard(),
    )
