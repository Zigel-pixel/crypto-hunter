"""External blockchain-data provider adapters."""


class ProviderError(RuntimeError):
    """Raised when a provider cannot return a wallet portfolio."""


class ProviderNotConfigured(ProviderError):
    """Raised when a provider's required environment variable is missing."""
