from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AssetDefinition:
    symbol: str
    name: str
    provider_id: str
    label: str

