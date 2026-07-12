from __future__ import annotations

import unittest

from app.services.asset_service import get_asset, list_supported_assets, search_assets
from app.utils.assets import ASSET_LABELS, COIN_IDS


class AssetRegistryTests(unittest.TestCase):
    def test_every_asset_has_unique_valid_provider_mapping(self) -> None:
        assets = list_supported_assets()
        self.assertEqual(len({asset.symbol for asset in assets}), len(assets))
        self.assertEqual(len({asset.provider_id for asset in assets}), len(assets))
        for asset in assets:
            self.assertEqual(COIN_IDS[asset.symbol], asset.provider_id)
            self.assertEqual(ASSET_LABELS[asset.symbol], asset.label)
            self.assertIs(get_asset(asset.provider_id), asset)

    def test_search_matches_name_and_ticker_case_insensitively(self) -> None:
        self.assertEqual(search_assets("btc")[0].provider_id, "bitcoin")
        self.assertEqual(search_assets("cardano")[0].symbol, "ADA")


if __name__ == "__main__":
    unittest.main()
