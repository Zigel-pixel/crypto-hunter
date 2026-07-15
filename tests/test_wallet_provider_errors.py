import asyncio

import aiohttp

from app.integrations.blockchain.errors import ProviderErrorCode, WalletProviderError, classify_provider_error
from app.utils.i18n import SUPPORTED_LANGUAGES, translate


def test_provider_error_classification() -> None:
    assert classify_provider_error(WalletProviderError(ProviderErrorCode.RATE_LIMITED)).value == "rate_limited"
    assert classify_provider_error(asyncio.TimeoutError()).value == "timeout"
    assert classify_provider_error(aiohttp.ClientConnectionError()).value == "provider_unavailable"
    assert classify_provider_error(RuntimeError()).value == "unknown_provider_error"


def test_every_provider_error_is_localized() -> None:
    for language in SUPPORTED_LANGUAGES:
        for code in ProviderErrorCode:
            assert translate(f"wallet.error.{code.value}", language) != f"wallet.error.{code.value}"
