from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class TokenContract:
    symbol: str
    address: str
    decimals: int
    standard: str


@dataclass(frozen=True)
class EvmNetwork:
    network_id: str
    display_name: str
    chain_id: int
    native_symbol: str
    rpc_env: str
    default_rpc_url: str | None
    explorer_url: str
    tokens: tuple[TokenContract, ...] = ()

    @property
    def rpc_url(self) -> str | None:
        value = os.getenv(self.rpc_env, "").strip()
        return value or self.default_rpc_url

    @property
    def enabled(self) -> bool:
        return bool(self.rpc_url)


ERC20 = "ERC-20"
NETWORKS: tuple[EvmNetwork, ...] = (
    EvmNetwork("ethereum", "Ethereum", 1, "ETH", "ETHEREUM_RPC_URL", "https://ethereum-rpc.publicnode.com", "https://etherscan.io", (
        TokenContract("USDT", "0xdAC17F958D2ee523a2206206994597C13D831ec7", 6, ERC20),
    )),
    EvmNetwork("bnb", "BNB Smart Chain", 56, "BNB", "BSC_RPC_URL", "https://bsc-rpc.publicnode.com", "https://bscscan.com"),
    EvmNetwork("polygon", "Polygon", 137, "POL", "POLYGON_RPC_URL", None, "https://polygonscan.com"),
    EvmNetwork("arbitrum", "Arbitrum One", 42161, "ETH", "ARBITRUM_RPC_URL", None, "https://arbiscan.io"),
    EvmNetwork("base", "Base", 8453, "ETH", "BASE_RPC_URL", None, "https://basescan.org"),
    EvmNetwork("optimism", "Optimism", 10, "ETH", "OPTIMISM_RPC_URL", None, "https://optimistic.etherscan.io"),
    EvmNetwork("avalanche", "Avalanche C-Chain", 43114, "AVAX", "AVALANCHE_RPC_URL", None, "https://snowtrace.io"),
)


def enabled_evm_networks() -> tuple[EvmNetwork, ...]:
    return tuple(network for network in NETWORKS if network.enabled)


def get_evm_network(network_id: str) -> EvmNetwork | None:
    return next((item for item in NETWORKS if item.network_id == network_id), None)
