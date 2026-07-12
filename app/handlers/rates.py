import asyncio

from aiogram import Router, types
from aiogram.filters import Command, StateFilter
from aiogram.types import (
    BufferedInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from app.handlers.common import user_main_keyboard
from app.handlers.message_updates import safe_update_message, safe_update_photo
from app.keyboards.main import action_labels, build_main_keyboard
from app.models.live_market import LiveQuote
from app.services.chart_service import build_crypto_chart, render_chart
from app.services.live_market_service import live_task_manager
from app.services.market_service import (
    CoinSnapshot,
    fetch_market_snapshots,
    format_compact_currency,
    format_compact_number,
    format_percent,
    format_price,
    format_supply,
    market_data_is_stale,
    market_refresh_in_progress,
)
from app.services.metals_service import METALS, fetch_metal, fetch_metal_history
from app.services.settings_service import get_setting
from app.utils.assets import ASSET_LABELS, COIN_IDS
from app.utils.timezones import format_market_time

router = Router()

COIN_OPTIONS = {
    coin_id: {"label": ASSET_LABELS[symbol], "symbol": symbol}
    for symbol, coin_id in COIN_IDS.items()
}


def build_rates_menu_keyboard(
    available_ids: set[str] | None = None,
    available_metals: set[str] | None = None,
) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text=(
                    meta["label"]
                    if available_ids is None or coin_id in available_ids
                    else f"❌ {meta['symbol']} unavailable"
                ),
                callback_data=f"rates:coin:{coin_id}",
            )
        ]
        for coin_id, meta in COIN_OPTIONS.items()
    ]
    buttons.extend(
        [
            InlineKeyboardButton(
                text=(
                    label
                    if available_metals is None or symbol in available_metals
                    else f"❌ {symbol} unavailable"
                ),
                callback_data=f"rates:metal:{symbol}",
            )
        ]
        for symbol, label in METALS.items()
    )
    buttons.append(
        [InlineKeyboardButton(text="⚡ Start Live", callback_data="rates:live:start")]
    )
    buttons.append(
        [InlineKeyboardButton(text="🔄 Refresh", callback_data="rates:refresh:menu")]
    )
    buttons.append([InlineKeyboardButton(text="⬅ Back", callback_data="rates:exit")])
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


def build_live_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏹ Stop Live", callback_data="rates:live:stop")],
            [InlineKeyboardButton(text="⬅ Back", callback_data="rates:live:back")],
        ]
    )


def build_live_text(quotes: dict[str, LiveQuote]) -> str:
    lines = ["⚡ Live Crypto / USDT", ""]
    for symbol in ("BTC", "ETH", "SOL", "BNB"):
        quote = quotes.get(symbol)
        lines.append(
            f"{symbol}/USDT: ${quote.price:,.2f}"
            if quote
            else f"{symbol}/USDT: connecting…"
        )
    latest = max((quote.updated_at for quote in quotes.values()), default=None)
    lines.extend(
        [
            "",
            "Source: Binance WebSocket",
            f"Updated: {latest.strftime('%H:%M:%S UTC') if latest else 'waiting for data'}",
        ]
    )
    return "\n".join(lines)


def build_coin_page_text(
    snapshot: CoinSnapshot,
    *,
    stale: bool = False,
    updated_at: str | None = None,
) -> str:
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
            (
                f"⚠️ Showing cached data from {updated_at or snapshot.updated_at}"
                if stale
                else f"🕒 Updated: {updated_at or snapshot.updated_at}"
            ),
            "",
            "Source: CoinGecko",
        ]
    )


async def send_rates_menu(
    target: types.Message | types.CallbackQuery,
    *,
    force_refresh: bool = False,
    callback_text: str | None = None,
    answer_callback: bool = True,
) -> None:
    market_result, metal_results = await asyncio.gather(
        fetch_market_snapshots(force_refresh=force_refresh),
        asyncio.gather(*(fetch_metal(symbol) for symbol in METALS)),
    )
    _, snapshots = market_result
    available_ids = set(snapshots) if snapshots else set()
    available_metals = {
        symbol
        for symbol, snapshot in zip(METALS, metal_results, strict=True)
        if snapshot is not None
    }
    text = (
        "📈 Rates\n\nChoose cryptocurrency or precious metal.\n"
        "Unavailable assets are marked clearly."
    )
    if market_data_is_stale():
        text += "\n⚠️ Cached market data is currently in use."
    markup = build_rates_menu_keyboard(available_ids, available_metals)
    if isinstance(target, types.CallbackQuery):
        await _update_callback_message(target, text, reply_markup=markup)
        if answer_callback:
            await target.answer(callback_text)
    else:
        await target.answer(text, reply_markup=markup)


async def show_coin_page(
    target: types.Message | types.CallbackQuery,
    coin_id: str,
    *,
    force_refresh: bool = False,
    callback_text: str | None = None,
    answer_callback: bool = True,
) -> None:
    updated_at, snapshots = await fetch_market_snapshots(force_refresh=force_refresh)

    if not updated_at or not snapshots or coin_id not in snapshots:
        text = "❌ Failed to fetch market data. Please try again later."
        if isinstance(target, types.CallbackQuery):
            await _update_callback_message(
                target, text, reply_markup=build_rates_menu_keyboard()
            )
            if answer_callback:
                await target.answer()
        else:
            await target.answer(text)
        return

    snapshot = snapshots[coin_id]
    timezone_name = await get_setting(target.from_user.id, "timezone")
    text = build_coin_page_text(
        snapshot,
        stale=market_data_is_stale(),
        updated_at=format_market_time(snapshot.updated_at, timezone_name),
    )
    markup = build_coin_keyboard(coin_id)
    chart = await build_crypto_chart(coin_id, snapshot.symbol.upper())

    if chart is not None:
        photo = BufferedInputFile(chart, filename=f"{coin_id}-24h.png")
        if isinstance(target, types.CallbackQuery):
            await _update_callback_photo(target, photo, text, markup)
            if answer_callback:
                await target.answer(callback_text)
        else:
            await target.answer_photo(photo, caption=text, reply_markup=markup)
    elif isinstance(target, types.CallbackQuery):
        await _update_callback_message(target, text, reply_markup=markup)
        if answer_callback:
            await target.answer(callback_text)
    else:
        await target.answer(text, reply_markup=markup)


async def show_metal_page(
    callback: types.CallbackQuery,
    symbol: str,
    *,
    answer_callback: bool = True,
) -> None:
    snapshot = await fetch_metal(symbol)
    if snapshot is None:
        if answer_callback:
            await callback.answer(
                "Metal data is temporarily unavailable.", show_alert=True
            )
        elif callback.message is not None:
            await callback.message.answer("Metal data is temporarily unavailable.")
        return
    history = await fetch_metal_history(symbol)
    text = "\n".join(
        [
            snapshot.name,
            "",
            "💵 Spot price per troy ounce",
            f"${snapshot.price:,.2f}",
            "",
            "🕒 Updated",
            snapshot.updated_at.strftime("%H:%M UTC"),
            "",
            f"Source: {snapshot.provider}",
        ]
    )
    markup = build_coin_keyboard(f"metal:{symbol}")
    if len(history) >= 2:
        chart = render_chart(history, f"{symbol}/USD — 30 days")
        await _update_callback_photo(
            callback,
            BufferedInputFile(chart, filename=f"{symbol.lower()}-30d.png"),
            text,
            markup,
        )
    else:
        await _update_callback_message(callback, text, reply_markup=markup)
    if answer_callback:
        await callback.answer()


async def _update_callback_message(
    callback: types.CallbackQuery,
    text: str,
    reply_markup: InlineKeyboardMarkup,
) -> None:
    """Safely update callback content regardless of text/media message type."""
    message = callback.message
    if message is None:
        return
    await safe_update_message(message, text, reply_markup)


async def _update_callback_photo(
    callback: types.CallbackQuery,
    photo: BufferedInputFile,
    caption: str,
    reply_markup: InlineKeyboardMarkup,
) -> None:
    message = callback.message
    if message is None:
        return
    await safe_update_photo(message, photo, caption, reply_markup)


@router.message(Command("rates"))
async def show_rates(message: types.Message) -> None:
    await send_rates_menu(message)


@router.message(lambda message: message.text in action_labels(0))
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
    chat_id = callback.message.chat.id if callback.message is not None else None
    if chat_id is not None and not data.startswith("rates:live:"):
        await live_task_manager.stop(chat_id)

    if data == "rates:live:start":
        if callback.message is None:
            await callback.answer()
            return
        message = callback.message
        await safe_update_message(message, build_live_text({}), build_live_keyboard())

        async def update_live(quotes: dict[str, LiveQuote]) -> None:
            await safe_update_message(
                message, build_live_text(quotes), build_live_keyboard()
            )

        started = await live_task_manager.start(message.chat.id, update_live)
        await callback.answer(
            "Live monitoring started"
            if started
            else "Live monitoring is already active"
        )
        return

    if data in {"rates:live:stop", "rates:live:back"}:
        if chat_id is not None:
            await live_task_manager.stop(chat_id)
        await send_rates_menu(callback)
        return

    if data == "rates:back":
        await send_rates_menu(callback)
        return

    if data == "rates:exit":
        if callback.message is not None:
            await safe_update_message(callback.message, "↩ Rates closed", None)
            await callback.message.answer(
                "↩ Main menu",
                reply_markup=await user_main_keyboard(callback.from_user.id),
            )
        await callback.answer()
        return

    if data.startswith("rates:coin:"):
        coin_id = data.split(":", 2)[2]
        await show_coin_page(callback, coin_id)
        return

    if data.startswith("rates:metal:"):
        await show_metal_page(callback, data.split(":", 2)[2])
        return

    if data.startswith("rates:refresh:"):
        if market_refresh_in_progress():
            await callback.answer("Updating…")
            return
        await callback.answer("Updating…")
        coin_id = data.split(":", 2)[2]
        if coin_id == "menu":
            await send_rates_menu(
                callback, force_refresh=True, answer_callback=False
            )
        elif coin_id.startswith("metal:"):
            await show_metal_page(
                callback, coin_id.split(":", 1)[1], answer_callback=False
            )
        else:
            await show_coin_page(
                callback,
                coin_id,
                force_refresh=True,
                answer_callback=False,
            )


@router.message(lambda message: message.text == "⬅ Back", StateFilter(None))
async def back_to_main(message: types.Message) -> None:
    await message.answer("↩ Returned to main menu.", reply_markup=build_main_keyboard())
