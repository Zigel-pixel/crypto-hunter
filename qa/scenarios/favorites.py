from app.services.asset_service import search_assets
from qa_bot.models import Scenario


async def search_check():
    queries = {query: [item.symbol for item in search_assets(query)] for query in ("Bitcoin", "BTC", " bit ", "bTc")}
    ok = all("BTC" in symbols for symbols in queries.values())
    return ok, str(queries), "Central asset catalog only"


def scenarios():
    return (Scenario("favorites.search", "Favorite asset search", "favorites", "Search by full, ticker, partial and case-insensitive input.", "Every query resolves Bitcoin", search_check, related_modules=("app/services/asset_service.py",)),)
