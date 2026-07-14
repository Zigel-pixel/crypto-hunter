from __future__ import annotations

import unittest

from app.integrations.blockchain.evm_rpc import _amount


class EvmRpcTests(unittest.TestCase):
    def test_token_decimal_conversion(self) -> None:
        self.assertEqual(_amount(hex(1_250_000), 6), 1.25)

    def test_malformed_amount_is_zero(self) -> None:
        self.assertEqual(_amount("not-hex", 18), 0.0)
