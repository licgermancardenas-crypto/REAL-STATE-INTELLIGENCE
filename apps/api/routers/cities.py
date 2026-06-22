from fastapi import APIRouter
from models.city import CityOut

router = APIRouter()

CITIES = [
    {"id": "caba", "name": "Ciudad de Buenos Aires", "lat": -34.6037, "lon": -58.3816, "zoom": 12},
    {"id": "rosario", "name": "Rosario", "lat": -32.9442, "lon": -60.6505, "zoom": 12},
    {"id": "cordoba", "name": "Córdoba", "lat": -31.4135, "lon": -64.1811, "zoom": 12},
    {"id": "mendoza", "name": "Mendoza", "lat": -32.8895, "lon": -68.8458, "zoom": 12},
]


@router.get("/", response_model=list[CityOut])
async def list_cities():
    return CITIES


@router.get("/{city_id}", response_model=CityOut)
async def get_city(city_id: str):
    city = next((c for c in CITIES if c["id"] == city_id), None)
    if not city:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="City not found")
    return city
