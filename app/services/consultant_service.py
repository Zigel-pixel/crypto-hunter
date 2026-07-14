"""Evidence-based crypto analysis using the project's free data sources."""

from __future__ import annotations

import asyncio
import logging
from collections import Counter

from app.integrations.blockchain.models import WalletSnapshot
from app.models.consultant import ConsultantIntent
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
from app.services.consultant_intent_service import classify_query

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


async def build_market_analysis(question: str | None = None, language: str = "Ukrainian") -> str:
    if question:
        return await answer_consultant_question(question)
    (_, snapshots), news = await asyncio.gather(
        fetch_market_snapshots(), get_news(NEWS_LIMIT)
    )
    if not snapshots:
        return ("❌ Ринкові дані тимчасово недоступні. Спробуйте пізніше."
                if language == "Ukrainian" else "❌ Market data is temporarily unavailable. Please try again later.")

    uk = language == "Ukrainian"
    lines = ["🤖 AI-консультант" if uk else "🤖 AI Consultant", "", "📊 Поточна картина ринку" if uk else "📊 Current market"]
    for coin_id in ("bitcoin", "ethereum", "solana", "binancecoin"):
        snapshot = snapshots.get(coin_id)
        if snapshot is not None:
            lines.append(_format_market_line(snapshot))

    sentiment, evidence = _news_sentiment(news)
    lines.extend(["", f"📰 Новинний фон: {sentiment}" if uk else "📰 News context (original headlines)"])
    if evidence:
        lines.extend(f"• {title}" for title in evidence[:3])

    btc = snapshots.get("bitcoin")
    lines.extend(["", "🧭 Сценарій" if uk else "🧭 Scenario", _build_scenario(btc, sentiment) if uk else _build_scenario_en(btc)])
    if question:
        lines.extend(["", "💬 Відповідь", _answer_question(question, snapshots, sentiment)])
    return "\n".join(lines)


def _build_scenario_en(btc: CoinSnapshot | None) -> str:
    change = btc.change_24h if btc else None
    if change is None:
        return "Price evidence is incomplete, so no reliable signal is available."
    if change >= STRONG_MOVE_PERCENT:
        return "BTC has already made a strong daily move. Chasing momentum increases entry risk; wait for confirmation or scale gradually."
    if change <= -STRONG_MOVE_PERCENT:
        return "BTC has fallen sharply. A lower price is not proof of a bottom; keep position sizing conservative and preserve cash reserves."
    return "There is no strong short-term signal. A cautious baseline is staged entries, defined risk, and no leverage."


async def answer_consultant_question(question: str, language: str | None = None) -> str:
    query = classify_query(question, language)
    uk = query.language == "Ukrainian"
    if query.intent is ConsultantIntent.STABLECOIN:
        return _stablecoin_answer(uk)
    if query.intent is ConsultantIntent.DEFI:
        return _defi_answer(uk)
    if query.intent is ConsultantIntent.CONCEPT and not query.assets:
        return ("🤖 Консультант\n\nУточніть, який термін або криптопродукт ви хочете розібрати. Я поясню принцип роботи, практичне застосування та основні ризики."
                if uk else "🤖 Consultant\n\nTell me which crypto term or product you want explained. I’ll cover how it works, practical uses, and its main risks.")
    _, snapshots = await fetch_market_snapshots()
    snapshots = snapshots or {}
    if query.intent is ConsultantIntent.COMPARISON:
        return _comparison_answer(query.assets, snapshots, uk)
    symbol = query.assets[0] if query.assets else "BTC"
    coin_id = {"BTC":"bitcoin", "ETH":"ethereum", "SOL":"solana", "BNB":"binancecoin"}.get(symbol)
    snapshot = snapshots.get(coin_id) if coin_id else None
    if snapshot is None:
        return "Зараз недостатньо актуальних даних для надійного висновку." if uk else "There is not enough current data for a reliable conclusion."
    return _asset_answer(snapshot, query.intent is ConsultantIntent.TRADING_DECISION, uk)


def _stablecoin_answer(uk: bool) -> str:
    if uk:
        return """🪙 Стейблкоїни

USDT і USDC — централізовані: зручні та ліквідні, але залежать від емітента, резервів, банків і регуляторних рішень. DAI більше спирається на ончейн-заставу, проте теж має ризики смартконтрактів і залежності від централізованих активів.

Основні ризики: втрата прив’язки до $1, непрозорі або недоступні резерви, блокування адрес емітентом, помилка мережі під час переказу, низька ліквідність і ризиковий DeFi-дохід.

Практично: перевіряйте мережу одержувача, диверсифікуйте великі суми між моделями/емітентами та не вважайте високий відсоток безризиковим."""
    return """🪙 Stablecoins

USDT and USDC are centralized: liquid and convenient, but exposed to issuer, reserve, banking, and regulatory risk. DAI relies more on on-chain collateral, while still carrying smart-contract and centralized-collateral exposure.

Main risks are depegging, inaccessible or unclear reserves, issuer address freezes, using the wrong transfer network, poor liquidity, and risky DeFi yield.

In practice: verify the recipient network, diversify large holdings across models/issuers, and never treat unusually high yield as risk-free."""


def _defi_answer(uk: bool) -> str:
    return ("DeFi — це фінансові сервіси у смартконтрактах без традиційного посередника. Основні ризики: помилки контрактів, злам, ліквідація застави, impermanent loss, маніпуляція оракулами та шахрайські токени. Починайте з малих сум і перевірених протоколів."
            if uk else "DeFi provides financial services through smart contracts without a traditional intermediary. Core risks include contract bugs, exploits, collateral liquidation, impermanent loss, oracle manipulation, and scam tokens. Start small and use established protocols.")


def _comparison_answer(symbols, snapshots, uk: bool) -> str:
    lines = ["⚖️ Порівняння" if uk else "⚖️ Comparison", ""]
    ids = {"BTC":"bitcoin", "ETH":"ethereum", "SOL":"solana", "BNB":"binancecoin"}
    for symbol in symbols[:2]:
        item = snapshots.get(ids.get(symbol, ""))
        lines.append(f"• {symbol}: {format_price(item.price)}, 24h {format_percent(item.change_24h)}" if item else f"• {symbol}: N/A")
    lines.append("\nЦіни за 24 години не визначають кращий довгостроковий актив; порівняйте призначення, децентралізацію, екосистему й допустимий ризик." if uk else "\nA 24-hour move does not determine the better long-term asset; compare purpose, decentralization, ecosystem, and acceptable risk.")
    return "\n".join(lines)


def _asset_answer(snapshot: CoinSnapshot, signal_requested: bool, uk: bool) -> str:
    change = snapshot.change_24h
    if not signal_requested:
        return (f"{snapshot.symbol.upper()}: {format_price(snapshot.price)}, зміна за 24г {format_percent(change)}. Це короткий ринковий зріз; для повного аналізу потрібні горизонт і мета позиції."
                if uk else f"{snapshot.symbol.upper()}: {format_price(snapshot.price)}, 24h change {format_percent(change)}. This is a short market snapshot; a full analysis needs your horizon and position objective.")
    signal = "WAIT" if change is None or abs(change) < 2 else ("HOLD" if change > 0 else "WAIT")
    confidence = 50 if change is None else min(70, 52 + int(abs(change)))
    return (f"Сигнал: {'ТРИМАТИ' if signal == 'HOLD' else 'ЧЕКАТИ'}\nВпевненість: {confidence}%\nГоризонт: 1–4 тижні\n\nПричина: {snapshot.symbol.upper()} змінився на {format_percent(change)} за 24г. Сценарій втратить актуальність, якщо напрям руху різко зміниться або з’явиться суттєва нова інформація."
            if uk else f"Signal: {signal}\nConfidence: {confidence}%\nHorizon: 1–4 weeks\n\nReason: {snapshot.symbol.upper()} moved {format_percent(change)} in 24h. The scenario is invalidated by a sharp reversal or material new information.")


async def build_wallet_analysis(telegram_id: int) -> str:
    wallets = await list_wallets(telegram_id)
    if not wallets:
        return (
            "👛 У вас ще немає збережених гаманців. Додайте їх у розділі Wallets."
            ""
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
        return "❌ Не вдалося отримати баланси гаманців."

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
