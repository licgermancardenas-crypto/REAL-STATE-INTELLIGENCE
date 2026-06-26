from fastapi import APIRouter
from ..data_loader import get_caba_geojson, get_gba_geojson, caba_stats, gba_stats

router = APIRouter(prefix="/cities", tags=["cities"])

_CITIES = {
    "caba": {
        "name": "Ciudad Autónoma de Buenos Aires",
        "short": "CABA",
        "loader": get_caba_geojson,
        "stats_fn": caba_stats,
        "score_type": "completo",
        "variables": 8,
        "center": [-58.44, -34.62],
        "zoom": 11.5,
    },
    "gba": {
        "name": "Gran Buenos Aires",
        "short": "GBA",
        "loader": get_gba_geojson,
        "stats_fn": gba_stats,
        "score_type": "parcial",
        "variables": 3,
        "center": [-58.65, -34.70],
        "zoom": 9.5,
    },
}


@router.get("/")
def list_cities():
    result = []
    for city_id, meta in _CITIES.items():
        data = meta["loader"]()
        available = data is not None
        entry = {
            "id": city_id,
            "name": meta["name"],
            "short": meta["short"],
            "score_type": meta["score_type"],
            "variables": meta["variables"],
            "center": meta["center"],
            "zoom": meta["zoom"],
            "available": available,
        }
        if available:
            stats = meta["stats_fn"]()
            entry["stats"] = stats
        result.append(entry)
    return {"cities": result}
