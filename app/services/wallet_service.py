"""Wallet business logic independent of blockchain API providers."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import datetime, timezone

import aiosqlite

from app.integrations.blockchain import bnb, bitcoin, ethereum, solana, tron
from app.integrations.blockchain.models import WalletSnapshot
from app.models.wallet import StoredWallet, WalletProfile
from app.models.wallet_address import AddressFamily
from app.models.wallet_discovery import WalletDiscoveryResult
from app.services.wallet_address_service import detect_wallet_address
from app.services.market_service import fetch_market_prices
from app.utils.config import WALLET_MAX_PER_USER

DB_NAME = "crypto.db"

NETWORK_LABELS: dict[str, str] = {
    "ethereum": "🔷 Ethereum",
    "bitcoin": "₿ Bitcoin",
    "bnb": "🟡 BNB Chain",
    "solana": "🟣 Solana",
    "tron": "🔴 Tron (TRX / USDT)",
}
NETWORK_TITLES: dict[str, str] = {
    "ethereum": "Ethereum",
    "bitcoin": "Bitcoin",
    "bnb": "BNB Chain",
    "solana": "Solana",
    "tron": "Tron",
}
PORTFOLIO_DIVIDER = "━━━━━━━━━━━━━━"
SHORT_ADDRESS_PREFIX_LENGTH = 6
SHORT_ADDRESS_SUFFIX_LENGTH = 4

logger = logging.getLogger(__name__)

WalletFetcher = Callable[[str], Awaitable[WalletSnapshot]]
AddressValidator = Callable[[str], bool]

_WALLET_FETCHERS: dict[str, WalletFetcher] = {
    "bitcoin": bitcoin.get_wallet,
    "ethereum": ethereum.get_wallet,
    "solana": solana.get_wallet,
    "bnb": bnb.get_wallet,
    "tron": tron.get_wallet,
}
_ADDRESS_VALIDATORS: dict[str, AddressValidator] = {
    "bitcoin": bitcoin.validate_address,
    "ethereum": ethereum.validate_address,
    "solana": solana.validate_address,
    "bnb": bnb.validate_address,
    "tron": tron.validate_address,
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
    detected = detect_wallet_address(address)
    normalized_address = (
        detected.comparison_address
        if detected and detected.family is AddressFamily.EVM
        else address.strip()
    )
    if not validate_wallet_address(normalized_network, normalized_address):
        raise ValueError(f"Invalid {normalized_network} wallet address")

    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            """
            INSERT INTO wallets (telegram_id, network, address, created_at)
            SELECT ?, ?, ?, ?
            WHERE NOT EXISTS (
                SELECT 1 FROM wallets
                WHERE telegram_id = ? AND network = ? AND lower(address) = lower(?)
            )
            """,
            (telegram_id, normalized_network, normalized_address, created_at,
             telegram_id, normalized_network, normalized_address),
        )
        await db.commit()
        return cursor.rowcount > 0


async def save_discovered_wallet(telegram_id: int, result: WalletDiscoveryResult) -> tuple[bool, int]:
    """Create/merge one address profile and its active networks without touching legacy rows."""
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    address = result.address.comparison_address
    family = result.address.family.value
    networks = [snapshot.chain for snapshot in result.active]
    if family == AddressFamily.TRON.value and not networks:
        networks = ["tron"]  # a valid zero-balance TRON address is still saveable
    async with aiosqlite.connect(DB_NAME) as db:
        count = (await (await db.execute(
            "SELECT count(*) FROM wallet_profiles WHERE telegram_id=?", (telegram_id,)
        )).fetchone())[0]
        cursor = await db.execute(
            "SELECT id FROM wallet_profiles WHERE telegram_id=? AND address_family=? AND address=? COLLATE NOCASE",
            (telegram_id, family, address),
        )
        row = await cursor.fetchone()
        created = row is None
        if created and count >= WALLET_MAX_PER_USER:
            raise ValueError("wallet_limit_reached")
        if row is None:
            cursor = await db.execute(
                "INSERT INTO wallet_profiles (telegram_id,address,address_family,created_at,last_refresh_at) VALUES (?,?,?,?,?)",
                (telegram_id, address, family, created_at, created_at),
            )
            wallet_id = cursor.lastrowid
        else:
            wallet_id = row[0]
            await db.execute("UPDATE wallet_profiles SET last_refresh_at=?,updated_at=? WHERE id=?", (created_at, created_at, wallet_id))
        added = 0
        for network in networks:
            cursor = await db.execute("INSERT OR IGNORE INTO wallet_networks (wallet_id,network) VALUES (?,?)", (wallet_id, network))
            added += cursor.rowcount
            # Keep legacy readers and removal UI working during the additive migration.
            await db.execute(
                "INSERT OR IGNORE INTO wallets (telegram_id,network,address,created_at) VALUES (?,?,?,?)",
                (telegram_id, network, address, created_at),
            )
        if result.active:
            snapshot = result.active[0]
            native = next((asset for asset in snapshot.assets if asset.symbol != "USDT"), None)
            usdt = next((asset for asset in snapshot.assets if asset.symbol == "USDT"), None)
            await db.execute(
                """UPDATE wallet_profiles SET last_refresh_at=?,updated_at=?,last_success_at=?,
                   native_balance=?,usdt_balance=?,native_symbol=?,balance_status='fresh',error_code=NULL
                   WHERE id=? AND telegram_id=?""",
                (created_at, created_at, created_at,
                 str(native.amount) if native else "0", str(usdt.amount) if usdt else "0",
                 native.symbol if native else ("TRX" if family == "tron" else "ETH"),
                 wallet_id, telegram_id),
            )
        elif result.warnings:
            # Preserve the last successful values; only status/error metadata changes.
            await db.execute(
                "UPDATE wallet_profiles SET last_refresh_at=?,updated_at=?,balance_status='stale',error_code='provider_unavailable' WHERE id=? AND telegram_id=?",
                (created_at, created_at, wallet_id, telegram_id),
            )
        await db.commit()
    return created, added


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


async def list_wallet_profiles(telegram_id: int) -> list[WalletProfile]:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("""
            SELECT p.id,p.address,p.address_family,p.label,p.last_refresh_at,n.network,
                   p.last_success_at,p.native_balance,p.usdt_balance,p.native_symbol,p.balance_status,p.error_code
            FROM wallet_profiles p LEFT JOIN wallet_networks n ON n.wallet_id=p.id
            WHERE p.telegram_id=? ORDER BY p.created_at,p.id,n.network
        """, (telegram_id,))
        rows = await cursor.fetchall()
    grouped: dict[int, list] = {}
    for row in rows:
        item = grouped.setdefault(row[0], [*row[:5], [], *row[6:]])
        if row[5]:
            item[5].append(row[5])
    return [WalletProfile(item[0], item[1], item[2], item[3], tuple(item[5]), item[4], *item[6:]) for item in grouped.values()]


async def get_wallet_profile(telegram_id: int, profile_id: int) -> WalletProfile | None:
    return next((item for item in await list_wallet_profiles(telegram_id) if item.id == profile_id), None)


async def rename_wallet_profile(telegram_id: int, profile_id: int, label: str) -> bool:
    cleaned = " ".join(label.split())
    if not 1 <= len(cleaned) <= 40 or any(ord(character) < 32 or ord(character) == 127 for character in label):
        raise ValueError("Wallet label must contain 1-40 characters")
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("UPDATE wallet_profiles SET label=? WHERE id=? AND telegram_id=?", (cleaned, profile_id, telegram_id))
        await db.commit()
        return cursor.rowcount > 0


async def delete_wallet_profile(telegram_id: int, profile_id: int) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        profile = await (await db.execute("SELECT address FROM wallet_profiles WHERE id=? AND telegram_id=?", (profile_id, telegram_id))).fetchone()
        if profile is None:
            return False
        await db.execute("DELETE FROM wallet_networks WHERE wallet_id=?", (profile_id,))
        cursor = await db.execute("DELETE FROM wallet_profiles WHERE id=? AND telegram_id=?", (profile_id, telegram_id))
        await db.execute("DELETE FROM wallets WHERE telegram_id=? AND address=? COLLATE NOCASE", (telegram_id, profile[0]))
        await db.commit()
        return cursor.rowcount > 0


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

    results = await asyncio.gather(
        *(get_wallet(wallet.network, wallet.address) for wallet in wallets),
        return_exceptions=True,
    )
    _, prices = await fetch_market_prices()

    lines = []
    for wallet, result in zip(wallets, results, strict=True):
        if isinstance(result, BaseException) and not isinstance(result, Exception):
            raise result
        if isinstance(result, BaseException):
            logger.warning("Could not load %s wallet: %s", wallet.network, result)
            lines.extend(_format_wallet_error(wallet.network, wallet.address))
            lines.append("")
            continue
        snapshot = _apply_market_prices(result, prices or {})
        lines.extend(_format_wallet_portfolio(snapshot))
        lines.append("")
    return "\n".join(lines).rstrip()


def _apply_market_prices(
    snapshot: WalletSnapshot, prices: dict[str, float]
) -> WalletSnapshot:
    assets = tuple(
        replace(
            asset,
            usd_value=(asset.amount * prices[asset.symbol])
            if asset.symbol in prices
            else asset.usd_value,
        )
        for asset in snapshot.assets
    )
    known_values = [asset.usd_value for asset in assets if asset.usd_value is not None]
    total = sum(known_values) if known_values and len(known_values) == len(assets) else None
    return replace(snapshot, assets=assets, total_usd_value=total)


def _format_wallet_portfolio(snapshot: WalletSnapshot) -> list[str]:
    network_title = _network_title(snapshot.chain)
    lines = [
        "💼 Portfolio",
        "",
        network_title,
        _format_address(snapshot.address),
        PORTFOLIO_DIVIDER,
    ]
    if not snapshot.assets:
        lines.extend(
            [
                "Wallet is empty.",
                "",
                "Last updated",
                _format_updated_at(snapshot.updated_at),
            ]
        )
        return lines

    for asset in snapshot.assets:
        label = f"{asset.symbol} ({asset.standard})" if asset.standard else asset.symbol
        lines.extend([label, _format_amount(asset.amount)])
        if asset.usd_value is not None:
            lines.append(_format_approx_usd(asset.usd_value))
        lines.append("")
    lines.extend(
        [
            PORTFOLIO_DIVIDER,
            "",
            "Total Portfolio Value",
            _format_usd(snapshot.total_usd_value),
            "",
            "Last updated",
            _format_updated_at(snapshot.updated_at),
        ]
    )
    return lines


def _format_wallet_error(network: str, address: str) -> list[str]:
    return [
        "💼 Portfolio",
        "",
        _network_title(network),
        _format_address(address),
        PORTFOLIO_DIVIDER,
        "",
        "Unable to retrieve wallet data.",
        "Please try again in a few moments.",
    ]


def _network_title(network: str) -> str:
    return NETWORK_TITLES.get(network, network.title())


def _format_amount(value: float) -> str:
    return f"{value:.8f}".rstrip("0").rstrip(".")


def _format_usd(value: float | None) -> str:
    return "N/A" if value is None else f"${value:,.2f}"


def _format_approx_usd(value: float) -> str:
    return f"≈ ${value:,.2f}"


def _format_address(address: str) -> str:
    if len(address) <= SHORT_ADDRESS_PREFIX_LENGTH + SHORT_ADDRESS_SUFFIX_LENGTH:
        return address
    return f"{address[:SHORT_ADDRESS_PREFIX_LENGTH]}...{address[-SHORT_ADDRESS_SUFFIX_LENGTH:]}"


def _format_updated_at(value: datetime | None) -> str:
    if value is None:
        return "N/A"
    return value.astimezone(timezone.utc).strftime("%H:%M UTC")
