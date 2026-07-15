from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from app.integrations.blockchain.models import WalletAsset, WalletSnapshot
from app.integrations.blockchain.network_registry import NETWORKS
from app.services.wallet_discovery_service import discover_wallet


ADDRESS = "0x" + "a" * 40


class WalletDiscoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_multiple_active_and_one_failure(self) -> None:
        enabled = NETWORKS[:3]
        async def fetch(network, address, timeout):
            if network.network_id == "bnb":
                raise RuntimeError("down")
            assets = ((WalletAsset("ETH", 1),) if network.network_id == "ethereum"
                      else (WalletAsset("USDC", 2, standard="ERC-20"),))
            return WalletSnapshot(network.network_id, address, assets, "test")
        with patch("app.services.wallet_discovery_service.enabled_evm_networks", return_value=enabled), patch("app.services.wallet_discovery_service.get_evm_wallet", fetch):
            result = await discover_wallet(ADDRESS, bypass_cooldown=True)
        self.assertEqual([item.chain for item in result.active], ["ethereum"])
        self.assertEqual(result.warnings, ())

    async def test_all_zero_is_valid(self) -> None:
        network = NETWORKS[:1]
        with patch("app.services.wallet_discovery_service.enabled_evm_networks", return_value=network), patch("app.services.wallet_discovery_service.get_evm_wallet", AsyncMock(return_value=WalletSnapshot("ethereum", ADDRESS, (), "test"))):
            result = await discover_wallet(ADDRESS, bypass_cooldown=True)
        self.assertEqual(result.active, ())
        self.assertEqual(result.scanned_networks, ("ethereum",))

    async def test_disabled_network_is_skipped_by_registry(self) -> None:
        with patch.dict("os.environ", {network.rpc_env: "" for network in NETWORKS}, clear=False):
            # Ethereum and BSC retain documented public defaults; optional networks do not.
            from app.integrations.blockchain.network_registry import enabled_evm_networks
            self.assertEqual([item.network_id for item in enabled_evm_networks()], ["ethereum", "bnb"])
