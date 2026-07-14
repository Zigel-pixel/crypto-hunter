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
from app.services.wallet_service import save_discovered_wallet


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
