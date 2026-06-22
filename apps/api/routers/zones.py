from fastapi import APIRouter, Query
from models.zone import ZoneOut, ZoneDetail

router = APIRouter()


@router.get("/{city_id}", response_model=list[ZoneOut])
async def list_zones(
    city_id: str,
    min_score: float = Query(default=0, ge=0, le=100),
    limit: int = Query(default=50, le=200),
):
    # TODO: query PostGIS — radios censales con alpha_score
    return []


@router.get("/{city_id}/{zone_id}", response_model=ZoneDetail)
async def get_zone(city_id: str, zone_id: str):
    # TODO: devuelve ficha completa de zona con drivers
    return {}
