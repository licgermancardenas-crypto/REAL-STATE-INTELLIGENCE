from pydantic import BaseModel
from typing import Any


class ZoneOut(BaseModel):
    zone_id: str
    city_id: str
    name: str
    alpha_score: float
    avg_price_usd_m2: float | None
    population: int | None
    geometry: dict[str, Any] | None  # GeoJSON geometry


class Driver(BaseModel):
    name: str
    impact: float  # -1.0 a +1.0
    description: str


class ZoneDetail(ZoneOut):
    drivers: list[Driver]
    price_trend_24m: float | None  # % proyectado
    comparable_zones: list[str]
