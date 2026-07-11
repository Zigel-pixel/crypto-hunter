from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.keyboards.main import build_main_keyboard
from app.services.market_service import (
    CoinSnapshot,
    fetch_market_snapshots,
    format_compact_currency,
    format_compact_number,
    format_percent,
    format_price,
    format_supply,
)

router = Router()

COIN_OPTIONS = {
    "bitcoin": {"label": "🟠 Bitcoin", "symbol": "BTC"},
    "ethereum": {"label": "🔵 Ethereum", "symbol": "ETH"},
    "solana": {"label": "🟣 Solana", "symbol": "SOL"},
}


def build_rates_menu_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text=meta["label"], callback_data=f"rates:coin:{coin_id}"
            )
        ]
        for coin_id, meta in COIN_OPTIONS.items()
    ]
    buttons.append(
        [InlineKeyboardButton(text="🔄 Refresh", callback_data="rates:refresh:menu")]
    )
    buttons.append([InlineKeyboardButton(text="⬅ Back", callback_data="rates:back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_coin_keyboard(coin_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Refresh", callback_data=f"rates:refresh:{coin_id}"
                )
            ],
            [InlineKeyboardButton(text="⬅ Back", callback_data="rates:back")],
        ]
    )


def build_coin_page_text(snapshot: CoinSnapshot) -> str:
    label = (
        COIN_OPTIONS[snapshot.id]["label"]
        if snapshot.id in COIN_OPTIONS
        else snapshot.name
    )
    percent_text = format_percent(snapshot.change_24h)
    percent_prefix = (
        "+" if snapshot.change_24h is not None and snapshot.change_24h >= 0 else ""
    )
    if snapshot.change_24h is not None and snapshot.change_24h >= 0:
        percent_line = f"📈 24h\n{percent_prefix}{percent_text}"
    else:
        percent_line = f"📈 24h\n{percent_text}"

    ath_change = "N/A"
    if snapshot.ath_change_percentage is not None:
        ath_change = f"{snapshot.ath_change_percentage:+.1f}%"

    return "\n".join(
        [
            label,
            "",
            "💵 Price",
            format_price(snapshot.price),
            "",
            percent_line,
            "",
            "🏆 Market Cap",
            format_compact_currency(snapshot.market_cap),
            "",
            "💸 Volume (24h)",
            format_compact_currency(snapshot.volume_24h),
            "",
            "⭐ Market Rank",
            f"#{snapshot.market_rank}" if snapshot.market_rank is not None else "N/A",
            "",
            "📊 Circulating Supply",
            format_supply(snapshot.circulating_supply, snapshot.symbol),
            "",
            "🏔 All Time High",
            format_price(snapshot.ath),
            "",
            "📉 From ATH",
            ath_change,
            "",
            "🕒 Updated",
            snapshot.updated_at,
        ]
    )


async def send_rates_menu(target: types.Message | types.CallbackQuery) -> None:
    updated_at, snapshots = await fetch_market_snapshots()

    if not updated_at or not snapshots:
        text = "❌ Failed to fetch market data. Please try again later."
        if isinstance(target, types.CallbackQuery):
            await target.message.edit_text(
                text, reply_markup=build_rates_menu_keyboard()
            )
            await target.answer()
        else:
            await target.answer(text)
        return

    text = "📈 Rates\n\nChoose coin"
    if isinstance(target, types.CallbackQuery):
        await target.message.edit_text(text, reply_markup=build_rates_menu_keyboard())
        await target.answer()
    else:
        await target.answer(text, reply_markup=build_rates_menu_keyboard())


async def show_coin_page(
    target: types.Message | types.CallbackQuery, coin_id: str
) -> None:
    updated_at, snapshots = await fetch_market_snapshots()

    if not updated_at or not snapshots or coin_id not in snapshots:
        text = "❌ Failed to fetch market data. Please try again later."
        if isinstance(target, types.CallbackQuery):
            await target.message.edit_text(
                text, reply_markup=build_rates_menu_keyboard()
            )
            await target.answer()
        else:
            await target.answer(text)
        return

    snapshot = snapshots[coin_id]
    text = build_coin_page_text(snapshot)
    markup = build_coin_keyboard(coin_id)

    if isinstance(target, types.CallbackQuery):
        await target.message.edit_text(text, reply_markup=markup)
        await target.answer()
    else:
        await target.answer(text, reply_markup=markup)


@router.message(Command("rates"))
async def show_rates(message: types.Message) -> None:
    await send_rates_menu(message)


@router.message(lambda message: message.text == "📈 Rates")
async def show_rates_button(message: types.Message) -> None:
    await send_rates_menu(message)


@router.message(lambda message: message.text == "🔄 Refresh")
async def refresh_rates(message: types.Message) -> None:
    await send_rates_menu(message)


@router.callback_query(
    lambda callback: callback.data and callback.data.startswith("rates:")
)
async def handle_rates_callback(callback: types.CallbackQuery) -> None:
    data = callback.data or ""
    if data == "rates:back":
        await send_rates_menu(callback)
        return

    if data.startswith("rates:coin:"):
        coin_id = data.split(":", 2)[2]
        await show_coin_page(callback, coin_id)
        return

    if data.startswith("rates:refresh:"):
        coin_id = data.split(":", 2)[2]
        if coin_id == "menu":
            await send_rates_menu(callback)
        else:
            await show_coin_page(callback, coin_id)


@router.message(lambda message: message.text == "⬅ Back")
async def back_to_main(message: types.Message) -> None:
    await message.answer("↩ Returned to main menu.", reply_markup=build_main_keyboard())
