"""Wallet business logic independent of blockchain API providers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
import logging

import aiosqlite

from app.integrations.blockchain import bnb, bitcoin, ethereum, solana
from app.integrations.blockchain.models import WalletSnapshot
from app.models.wallet import StoredWallet

DB_NAME = "crypto.db"

NETWORK_LABELS: dict[str, str] = {
    "ethereum": "🔷 Ethereum",
    "bitcoin": "₿ Bitcoin",
    "bnb": "🟡 BNB Chain",
    "solana": "🟣 Solana",
}
NETWORK_TITLES: dict[str, str] = {
    "ethereum": "Ethereum",
    "bitcoin": "Bitcoin",
    "bnb": "BNB Chain",
    "solana": "Solana",
}
PORTFOLIO_DIVIDER = "━━━━━━━━━━━━━━"

logger = logging.getLogger(__name__)

WalletFetcher = Callable[[str], Awaitable[WalletSnapshot]]
AddressValidator = Callable[[str], bool]

_WALLET_FETCHERS: dict[str, WalletFetcher] = {
    "bitcoin": bitcoin.get_wallet,
    "ethereum": ethereum.get_wallet,
    "solana": solana.get_wallet,
    "bnb": bnb.get_wallet,
}
_ADDRESS_VALIDATORS: dict[str, AddressValidator] = {
    "bitcoin": bitcoin.validate_address,
    "ethereum": ethereum.validate_address,
    "solana": solana.validate_address,
    "bnb": bnb.validate_address,
}


def supported_chains() -> tuple[str, ...]:
    return tuple(_WALLET_FETCHERS)


def validate_wallet_address(chain: str, address: str) -> bool:
    validator = _ADDRESS_VALIDATORS.get(chain.lower())
    return bool(validator and validator(address))


async def get_wallet(chain: str, address: str) -> WalletSnapshot:
    normalized_chain = chain.lower()
    fetcher = _WALLET_FETCHERS.get(normalized_chain)
    if fetcher is None:
        raise ValueError(f"Unsupported blockchain: {chain}")
    if not validate_wallet_address(normalized_chain, address):
        raise ValueError(f"Invalid {normalized_chain} wallet address")
    return await fetcher(address)


async def add_wallet(telegram_id: int, network: str, address: str) -> bool:
    normalized_network = network.lower()
    normalized_address = address.strip()
    if not validate_wallet_address(normalized_network, normalized_address):
        raise ValueError(f"Invalid {normalized_network} wallet address")

    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            """
            INSERT OR IGNORE INTO wallets (telegram_id, network, address, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (telegram_id, normalized_network, normalized_address, created_at),
        )
        await db.commit()
        return cursor.rowcount > 0


async def list_wallets(telegram_id: int) -> list[StoredWallet]:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            """
            SELECT network, address
            FROM wallets
            WHERE telegram_id = ?
            ORDER BY created_at, id
            """,
            (telegram_id,),
        )
        rows = await cursor.fetchall()
    return [StoredWallet(network=row[0], address=row[1]) for row in rows]


async def remove_wallet(telegram_id: int, network: str, address: str) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            """
            DELETE FROM wallets
            WHERE telegram_id = ? AND network = ? AND address = ?
            """,
            (telegram_id, network.lower(), address),
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_wallets_text(telegram_id: int) -> str:
    wallets = await list_wallets(telegram_id)
    if not wallets:
        return "👛 No wallets added yet."

    lines = []
    for wallet in wallets:
        try:
            snapshot = await get_wallet(wallet.network, wallet.address)
        except Exception as exc:
            logger.warning("Could not load %s wallet: %s", wallet.network, exc)
            lines.extend(_format_wallet_error(wallet.network, wallet.address))
            lines.append("")
            continue

        lines.extend(_format_wallet_portfolio(snapshot))
        lines.append("")
    return "\n".join(lines).rstrip()


def _format_wallet_portfolio(snapshot: WalletSnapshot) -> list[str]:
    network_title = _network_title(snapshot.chain)
    lines = [
        "💼 Portfolio",
        "",
        "Address",
        snapshot.address,
        "",
        "Network",
        network_title,
        "",
        PORTFOLIO_DIVIDER,
    ]
    if not snapshot.assets:
        lines.append("Wallet is empty.")
        return lines

    for asset in snapshot.assets:
        lines.extend([asset.symbol, _format_amount(asset.amount)])
        if asset.usd_value is not None:
            lines.append(_format_usd(asset.usd_value))
        lines.append("")
    lines.extend(
        [
            PORTFOLIO_DIVIDER,
            "",
            "Total Portfolio Value",
            _format_usd(snapshot.total_usd_value),
        ]
    )
    return lines


def _format_wallet_error(network: str, address: str) -> list[str]:
    return [
        "💼 Portfolio",
        "",
        "Address",
        address,
        "",
        "Network",
        _network_title(network),
        "",
        "❌ Unable to load wallet portfolio. Please try again later.",
    ]


def _network_title(network: str) -> str:
    return NETWORK_TITLES.get(network, network.title())


def _format_amount(value: float) -> str:
    return f"{value:.8f}".rstrip("0").rstrip(".")


def _format_usd(value: float | None) -> str:
    return "N/A" if value is None else f"${value:,.2f}"
