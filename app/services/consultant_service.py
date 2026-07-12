"""Evidence-based crypto analysis using the project's free data sources."""

from __future__ import annotations

import asyncio
import logging
from collections import Counter

from app.integrations.blockchain.models import WalletSnapshot
from app.models.news import NewsItem
from app.services.market_service import (
    CoinSnapshot,
    fetch_market_prices,
    fetch_market_snapshots,
    format_percent,
    format_price,
)
from app.services.news_service import get_news
from app.services.wallet_service import get_wallet, list_wallets

DISCLAIMER = (
    "⚠️ Це інформаційний аналіз, не персональна фінансова рекомендація. "
    "Криптоактиви високоризикові."
)
NEWS_LIMIT = 7
STRONG_MOVE_PERCENT = 5.0
MODERATE_MOVE_PERCENT = 2.0

POSITIVE_WORDS = {
    "adoption", "approval", "approved", "boost", "bull", "gain", "growth",
    "high", "launch", "rally", "record", "surge", "win",
}
NEGATIVE_WORDS = {
    "attack", "ban", "bear", "collapse", "conflict", "crash", "drop",
    "fall", "fraud", "hack", "lawsuit", "risk", "selloff", "war",
}

logger = logging.getLogger(__name__)


async def build_market_analysis(question: str | None = None) -> str:
    (_, snapshots), news = await asyncio.gather(
        fetch_market_snapshots(), get_news(NEWS_LIMIT)
    )
    if not snapshots:
        return (
            "❌ Ринкові дані тимчасово недоступні. Спробуйте пізніше.\n\n"
            f"{DISCLAIMER}"
        )

    lines = ["🤖 AI-консультант", "", "📊 Поточна картина ринку"]
    for coin_id in ("bitcoin", "ethereum", "solana", "binancecoin"):
        snapshot = snapshots.get(coin_id)
        if snapshot is not None:
            lines.append(_format_market_line(snapshot))

    sentiment, evidence = _news_sentiment(news)
    lines.extend(["", f"📰 Новинний фон: {sentiment}"])
    if evidence:
        lines.extend(f"• {title}" for title in evidence[:3])

    btc = snapshots.get("bitcoin")
    lines.extend(["", "🧭 Сценарій", _build_scenario(btc, sentiment)])
    if question:
        lines.extend(["", "💬 Відповідь", _answer_question(question, snapshots, sentiment)])
    lines.extend(["", DISCLAIMER])
    return "\n".join(lines)


async def build_wallet_analysis(telegram_id: int) -> str:
    wallets = await list_wallets(telegram_id)
    if not wallets:
        return (
            "👛 У вас ще немає збережених гаманців. Додайте їх у розділі Wallets."
            f"\n\n{DISCLAIMER}"
        )

    wallet_results, (_, prices) = await asyncio.gather(
        asyncio.gather(
            *(get_wallet(wallet.network, wallet.address) for wallet in wallets),
            return_exceptions=True,
        ),
        fetch_market_prices(),
    )
    results = list(wallet_results)
    snapshots = [result for result in results if isinstance(result, WalletSnapshot)]
    failed = len(results) - len(snapshots)
    if not snapshots:
        return f"❌ Не вдалося отримати баланси гаманців.\n\n{DISCLAIMER}"

    amounts: Counter[str] = Counter()
    networks: set[str] = set()
    for snapshot in snapshots:
        networks.add(snapshot.chain)
        for asset in snapshot.assets:
            amounts[asset.symbol] += asset.amount

    lines = ["🤖 Аналіз гаманців", ""]
    if amounts:
        total_usd = 0.0
        complete_valuation = True
        for symbol, amount in sorted(amounts.items()):
            amount_text = f"{amount:.8f}".rstrip("0").rstrip(".")
            price = (prices or {}).get(symbol)
            if price is None:
                complete_valuation = False
                lines.append(f"• {symbol}: {amount_text}")
                continue
            usd_value = amount * price
            total_usd += usd_value
            lines.append(f"• {symbol}: {amount_text} ≈ ${usd_value:,.2f}")
        if complete_valuation:
            lines.extend(["", f"Орієнтовна загальна вартість: ${total_usd:,.2f}"])
    else:
        lines.append("Збережені гаманці зараз мають нульовий нативний баланс.")
    lines.extend(["", f"Мереж у портфелі: {len(networks)}."])
    lines.append(_diversification_note(amounts))
    if failed:
        lines.append(f"Не вдалося оновити гаманців: {failed}.")
    lines.extend(["", DISCLAIMER])
    return "\n".join(lines)


def _format_market_line(snapshot: CoinSnapshot) -> str:
    return (
        f"• {snapshot.symbol.upper()}: {format_price(snapshot.price)} "
        f"({format_percent(snapshot.change_24h)} за 24г)"
    )


def _news_sentiment(news: list[NewsItem]) -> tuple[str, list[str]]:
    score = 0
    evidence: list[str] = []
    for item in news:
        words = {word.strip(".,:;!?()[]\"'").lower() for word in item.title.split()}
        item_score = len(words & POSITIVE_WORDS) - len(words & NEGATIVE_WORDS)
        score += item_score
        if item_score != 0:
            evidence.append(item.title)
    if score >= 2:
        return "помірно позитивний", evidence
    if score <= -2:
        return "підвищено негативний", evidence
    return "змішаний/нейтральний", evidence


def _build_scenario(btc: CoinSnapshot | None, sentiment: str) -> str:
    change = btc.change_24h if btc else None
    if change is None:
        return "Ціновий сигнал неповний — краще не робити висновок лише з новин."
    if change <= -STRONG_MOVE_PERCENT:
        return (
            "BTC уже різко знизився. Це може дати нижчу ціну входу, але ловити дно "
            "ризиковано; розумніший сценарій — невеликі частини покупки та резерв кешу."
        )
    if change >= STRONG_MOVE_PERCENT:
        return (
            "BTC має сильний денний ріст. Купівля після імпульсу підвищує ризик входу "
            "на локальному піку; варто дочекатися підтвердження або заходити частинами."
        )
    if "негативний" in sentiment:
        return (
            "Новинний ризик підвищений, але ціна ще не показує сильного руху. "
            "Новина сама по собі не доводить майбутнє падіння; потрібне підтвердження ринком."
        )
    return (
        "Сильного короткострокового сигналу немає. Базовий обережний підхід — DCA, "
        "ліміт ризику та відмова від кредитного плеча."
    )


def _answer_question(
    question: str, snapshots: dict[str, CoinSnapshot], sentiment: str
) -> str:
    normalized = question.lower()
    coin_id = next(
        (
            coin
            for coin, aliases in {
                "bitcoin": ("bitcoin", "btc", "біт", "бит"),
                "ethereum": ("ethereum", "eth", "ефір", "эфир"),
                "solana": ("solana", "sol", "солан"),
                "binancecoin": ("bnb", "binance"),
            }.items()
            if any(alias in normalized for alias in aliases)
        ),
        "bitcoin",
    )
    snapshot = snapshots.get(coin_id)
    if snapshot is None:
        return "Для цього активу зараз недостатньо актуальних даних."
    change = snapshot.change_24h
    if any(word in normalized for word in ("куп", "buy", "заход", "entry")):
        if change is not None and change >= MODERATE_MOVE_PERCENT:
            return (
                f"{snapshot.symbol.upper()} уже виріс {format_percent(change)} за 24г. "
                "Не бачу підстав радити вхід усією сумою; розгляньте DCA і ліміт збитку."
            )
        if change is not None and change <= -MODERATE_MOVE_PERCENT:
            return (
                f"{snapshot.symbol.upper()} знизився {format_percent(change)} за 24г. "
                "Ціна нижча, але падіння може продовжитися; можливий лише поетапний вхід "
                "сумою, втрату якої ви витримаєте."
            )
    return (
        f"{snapshot.symbol.upper()} зараз {format_price(snapshot.price)}, зміна за 24г: "
        f"{format_percent(change)}. Новинний фон — {sentiment}. Цього недостатньо для "
        "надійного прогнозу; оцініть горизонт, частку активу й допустиму просадку."
    )


def _diversification_note(amounts: Counter[str]) -> str:
    if len(amounts) <= 1 and amounts:
        return "Портфель сконцентрований в одному активі — ризик просадки вищий."
    if len(amounts) > 1:
        return "Є розподіл між активами, але суми в різних монетах без USD-ваг не порівнюються."
    return "Для оцінки ризику потрібен ненульовий баланс."
