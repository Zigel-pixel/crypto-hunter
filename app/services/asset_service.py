from __future__ import annotations

from app.models.asset import AssetDefinition
from app.services.market_service import CoinSnapshot, fetch_market_snapshots
from app.utils.assets import ASSET_REGISTRY


def list_supported_assets() -> tuple[AssetDefinition, ...]:
    return ASSET_REGISTRY


def search_assets(query: str) -> list[AssetDefinition]:
    normalized = query.strip().casefold()
    if not normalized:
        return []
    return [
        asset
        for asset in ASSET_REGISTRY
        if normalized in asset.symbol.casefold() or normalized in asset.name.casefold()
    ]


def get_asset(provider_id: str) -> AssetDefinition | None:
    return next(
        (asset for asset in ASSET_REGISTRY if asset.provider_id == provider_id), None
    )


async def get_asset_snapshot(
    provider_id: str, *, force_refresh: bool = False
) -> CoinSnapshot | None:
    _, snapshots = await fetch_market_snapshots(force_refresh=force_refresh)
    return snapshots.get(provider_id) if snapshots else None
