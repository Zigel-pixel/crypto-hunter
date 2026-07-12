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

    lines = ["👛 Your Wallets", ""]
    for wallet in wallets:
        network_label = NETWORK_LABELS.get(wallet.network, wallet.network.title())
        try:
            snapshot = await get_wallet(wallet.network, wallet.address)
        except Exception as exc:
            logger.warning("Could not load %s wallet: %s", wallet.network, exc)
            lines.extend(
                [network_label, wallet.address, "Balance unavailable", ""]
            )
            continue

        lines.extend(
            [NETWORK_LABELS.get(snapshot.chain, snapshot.chain.title()), snapshot.address]
            + [f"• {asset.symbol}: {asset.amount:.8f}" for asset in snapshot.assets]
            + [""]
        )
    return "\n".join(lines).rstrip()
