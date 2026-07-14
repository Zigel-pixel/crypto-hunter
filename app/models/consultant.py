from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ConsultantIntent(StrEnum):
    CONCEPT = "concept"
    ASSET_ANALYSIS = "asset_analysis"
    COMPARISON = "comparison"
    STABLECOIN = "stablecoin"
    DEFI = "defi"
    TRADING_DECISION = "trading_decision"
    MARKET_OVERVIEW = "market_overview"


@dataclass(frozen=True)
class ConsultantQuery:
    text: str
    intent: ConsultantIntent
    assets: tuple[str, ...]
    language: str
