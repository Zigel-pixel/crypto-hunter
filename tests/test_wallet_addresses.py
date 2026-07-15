from __future__ import annotations

import unittest

from app.models.wallet_address import AddressFamily
from app.services.wallet_address_service import detect_wallet_address


class WalletAddressTests(unittest.TestCase):
    def test_whitespace_contaminated_evm_is_rejected(self) -> None:
        address = "0x52908400098527886E0F7030069857D2E4169EE7"
        result = detect_wallet_address(f"  {address}\n")
        self.assertIsNone(result)

    def test_evm_is_normalized_for_comparison(self) -> None:
        address = "0x52908400098527886E0F7030069857D2E4169EE7"
        result = detect_wallet_address(address)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.family, AddressFamily.EVM)
        self.assertEqual(result.comparison_address, address.lower())

    def test_lowercase_evm_is_valid(self) -> None:
        self.assertIsNotNone(detect_wallet_address("0x" + "a" * 40))

    def test_valid_and_invalid_eip55(self) -> None:
        valid = "0x52908400098527886E0F7030069857D2E4169EE7"
        self.assertIsNotNone(detect_wallet_address(valid))
        self.assertIsNone(detect_wallet_address(valid.replace("E", "e", 1)))

    def test_uppercase_evm_is_valid(self) -> None:
        self.assertIsNotNone(detect_wallet_address("0x" + "ABCDEF" * 6 + "ABCD"))

    def test_internal_whitespace_is_invalid(self) -> None:
        self.assertIsNone(detect_wallet_address("0x" + "a" * 20 + " " + "a" * 20))

    def test_malformed_evm_is_invalid(self) -> None:
        self.assertIsNone(detect_wallet_address("0x" + "g" * 40))
        self.assertIsNone(detect_wallet_address("0x1234"))

    def test_tron_uses_base58check(self) -> None:
        valid = "TXLAQ63Xg1NAzckPwKHvzw7CSEmLMEqcdj"
        result = detect_wallet_address(valid)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.family, AddressFamily.TRON)
        self.assertIsNone(detect_wallet_address(valid[:-1] + "k"))

    def test_unsupported_format_is_invalid(self) -> None:
        self.assertIsNone(detect_wallet_address("not-a-wallet"))


if __name__ == "__main__":
    unittest.main()
