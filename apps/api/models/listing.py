from pydantic import BaseModel
from datetime import date


class ListingOut(BaseModel):
    id: str
    city_id: str
    address: str
    lat: float
    lon: float
    property_type: str  # depto, casa, ph, lote, local
    price_usd: float
    surface_m2: float
    price_usd_m2: float
    rooms: int | None
    source: str         # zonaprop, argenprop
    scraped_at: date
    zone_id: str | None
    alpha_score: float | None
