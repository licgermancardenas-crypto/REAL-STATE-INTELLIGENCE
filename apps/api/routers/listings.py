from fastapi import APIRouter, Query
from models.listing import ListingOut

router = APIRouter()


@router.get("/{city_id}", response_model=list[ListingOut])
async def list_listings(
    city_id: str,
    property_type: str = Query(default="all"),
    min_price_usd: float | None = None,
    max_price_usd: float | None = None,
    limit: int = Query(default=100, le=500),
):
    # TODO: query scraped listings from Zonaprop/Argenprop
    return []
