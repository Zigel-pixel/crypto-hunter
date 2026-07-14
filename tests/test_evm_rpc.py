from __future__ import annotations

import unittest
import asyncio
from unittest.mock import patch

from app.integrations.blockchain.evm_rpc import EvmRpcError, _amount, _rpc, get_wallet
from app.integrations.blockchain.network_registry import EvmNetwork, TokenContract


class EvmRpcTests(unittest.TestCase):
    def test_token_decimal_conversion(self) -> None:
        self.assertEqual(_amount(hex(1_250_000), 6), 1.25)

    def test_malformed_amount_is_zero(self) -> None:
        self.assertIsNone(_amount("not-hex", 18))

    def test_native_zero_and_positive_balance(self) -> None:
        self.assertEqual(_amount("0x0", 18), 0.0)
        self.assertEqual(_amount(hex(2 * 10**18), 18), 2.0)

    def test_wrong_result_type_is_invalid(self) -> None:
        self.assertIsNone(_amount(123, 18))


class _Response:
    def __init__(self, payload): self.payload, self.status = payload, 200
    async def __aenter__(self): return self
    async def __aexit__(self, *args): return None
    async def json(self): return self.payload


class _Session:
    def __init__(self, responses): self.responses = iter(responses)
    async def __aenter__(self): return self
    async def __aexit__(self, *args): return None
    def post(self, *args, **kwargs): return _Response(next(self.responses))


class _TimeoutSession:
    def post(self, *args, **kwargs):
        raise asyncio.TimeoutError


class EvmRpcResponseTests(unittest.IsolatedAsyncioTestCase):
    async def test_rpc_rejects_error_and_cross_request_id(self) -> None:
        with self.assertRaises(EvmRpcError):
            await _rpc(_Session([{"jsonrpc": "2.0", "id": 1, "error": {"code": -1}}]), "url", "x", [], 1)
        with self.assertRaises(EvmRpcError):
            await _rpc(_Session([{"jsonrpc": "2.0", "id": 99, "result": "0x0"}]), "url", "x", [], 1)

    async def test_provider_timeout_is_wrapped(self) -> None:
        with self.assertRaisesRegex(EvmRpcError, "RPC request failed"):
            await _rpc(_TimeoutSession(), "url", "x", [], 1)

    async def test_partial_token_failure_preserves_native_and_warning(self) -> None:
        network = EvmNetwork("test", "Test Network", 9, "TST", "TEST_RPC", "https://rpc", "https://explorer", (
            TokenContract("USDT", "0x" + "1" * 40, 6, "ERC-20"),
        ))
        responses = [{"jsonrpc": "2.0", "id": 1, "result": hex(10**18)}, {"jsonrpc": "2.0", "id": 2, "result": "malformed"}]
        with patch("app.integrations.blockchain.evm_rpc.aiohttp.ClientSession", return_value=_Session(responses)):
            result = await get_wallet(network, "0x" + "0" * 40, 5)
        self.assertEqual(result.assets[0].amount, 1.0)
        self.assertIn("USDT", result.warnings[0])
