from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import aiosqlite

from app.database.database import init_db
from app.integrations.blockchain.models import WalletAsset, WalletSnapshot
from app.models.wallet_discovery import WalletDiscoveryResult
from app.services.wallet_address_service import detect_wallet_address
from app.services.wallet_service import delete_wallet_profile, list_wallet_profiles, rename_wallet_profile, save_discovered_wallet


class WalletPersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_merge_preserves_profile_and_adds_network(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db_name = str(Path(directory) / "test.db")
            with patch("app.database.database.DB_NAME", db_name):
                await init_db()
                await init_db()  # migration is idempotent
            address = detect_wallet_address("0x" + "a" * 40)
            first = WalletDiscoveryResult(address, ("ethereum",), (WalletSnapshot("ethereum", address.display_address, (WalletAsset("ETH", 1),), "test"),))
            second = WalletDiscoveryResult(address, ("ethereum", "base"), (WalletSnapshot("base", address.display_address, (WalletAsset("ETH", 2),), "test"),))
            with patch("app.services.wallet_service.DB_NAME", db_name):
                self.assertEqual(await save_discovered_wallet(7, first), (True, 1))
                self.assertEqual(await save_discovered_wallet(7, second), (False, 1))
            async with aiosqlite.connect(db_name) as db:
                profile_count = (await (await db.execute("SELECT count(*) FROM wallet_profiles")).fetchone())[0]
                networks = [row[0] for row in await (await db.execute("SELECT network FROM wallet_networks ORDER BY network")).fetchall()]
            self.assertEqual(profile_count, 1)
            self.assertEqual(networks, ["base", "ethereum"])

    async def test_rename_and_repeated_profile_delete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db_name = str(Path(directory) / "test.db")
            with patch("app.database.database.DB_NAME", db_name):
                await init_db()
            address = detect_wallet_address("0x" + "b" * 40)
            result = WalletDiscoveryResult(address, ("ethereum",), (WalletSnapshot("ethereum", address.display_address, (WalletAsset("ETH", 1),), "test"),))
            with patch("app.services.wallet_service.DB_NAME", db_name):
                await save_discovered_wallet(8, result)
                profile = (await list_wallet_profiles(8))[0]
                self.assertTrue(await rename_wallet_profile(8, profile.id, " Main wallet "))
                renamed = (await list_wallet_profiles(8))[0]
                self.assertEqual(renamed.label, "Main wallet")
                self.assertTrue(await delete_wallet_profile(8, profile.id))
                self.assertFalse(await delete_wallet_profile(8, profile.id))

    async def test_duplicate_limit_ownership_and_stale_preserves_balance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db_name = str(Path(directory) / "test.db")
            with patch("app.database.database.DB_NAME", db_name):
                await init_db()
            address = detect_wallet_address("0x" + "c" * 40)
            success = WalletDiscoveryResult(address, ("ethereum",), (WalletSnapshot(
                "ethereum", address.display_address,
                (WalletAsset("ETH", 1), WalletAsset("USDT", 2, standard="ERC-20")), "test"),))
            failed = WalletDiscoveryResult(address, ("ethereum",), (), ("timeout",), True)
            with patch("app.services.wallet_service.DB_NAME", db_name), patch("app.services.wallet_service.WALLET_MAX_PER_USER", 1):
                self.assertEqual(await save_discovered_wallet(10, success), (True, 1))
                self.assertEqual(await save_discovered_wallet(10, success), (False, 0))
                await save_discovered_wallet(10, failed)
                profile = (await list_wallet_profiles(10))[0]
                self.assertEqual((profile.native_balance, profile.usdt_balance), ("1", "2"))
                self.assertEqual((profile.balance_status, profile.error_code), ("stale", "timeout"))
                self.assertEqual(await list_wallet_profiles(11), [])
                second = detect_wallet_address("0x" + "d" * 40)
                with self.assertRaisesRegex(ValueError, "wallet_limit_reached"):
                    await save_discovered_wallet(10, WalletDiscoveryResult(second, ("ethereum",), ()))
