from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AddressFamily(StrEnum):
    EVM = "evm"
    TRON = "tron"


@dataclass(frozen=True)
class NormalizedWalletAddress:
    display_address: str
    comparison_address: str
    family: AddressFamily
