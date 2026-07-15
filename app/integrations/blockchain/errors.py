from __future__ import annotations

import asyncio
from enum import StrEnum

import aiohttp


class ProviderErrorCode(StrEnum):
    PROVIDER_NOT_CONFIGURED = "provider_not_configured"
    INVALID_ADDRESS = "invalid_address"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    MALFORMED_RESPONSE = "malformed_response"
    UNSUPPORTED_NETWORK = "unsupported_network"
    CONTRACT_ERROR = "contract_error"
    UNKNOWN_PROVIDER_ERROR = "unknown_provider_error"


class WalletProviderError(RuntimeError):
    def __init__(self, code: ProviderErrorCode, message: str = "Wallet provider failed") -> None:
        super().__init__(message)
        self.code = code


def classify_provider_error(error: BaseException) -> ProviderErrorCode:
    if isinstance(error, WalletProviderError):
        return error.code
    if isinstance(error, (asyncio.TimeoutError, TimeoutError)):
        return ProviderErrorCode.TIMEOUT
    if isinstance(error, aiohttp.ClientResponseError) and error.status == 429:
        return ProviderErrorCode.RATE_LIMITED
    if isinstance(error, aiohttp.ClientError):
        return ProviderErrorCode.PROVIDER_UNAVAILABLE
    return ProviderErrorCode.UNKNOWN_PROVIDER_ERROR
