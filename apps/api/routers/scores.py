from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Query
from ..data_loader import get_caba_geojson, get_gba_geojson, get_gap_geojson, caba_stats, gba_stats

router = APIRouter(prefix="/scores", tags=["scores"])

CITY_LOADERS = {
    "caba": get_caba_geojson,
    "gba":  get_gba_geojson,
}

CITY_STATS = {
    "caba": caba_stats,
    "gba":  gba_stats,
}


@router.get("/{city}")
def get_city_scores(
    city: str,
    quintil: Optional[int] = Query(None, ge=1, le=5, description="Filtrar por quintil (1-5)"),
    min_score: Optional[float] = Query(None, ge=0, le=100),
    max_score: Optional[float] = Query(None, ge=0, le=100),
    limit: int = Query(500, ge=1, le=5000),
    geojson: bool = Query(True, description="Devolver GeoJSON completo (True) o solo properties (False)"),
) -> Any:
    if city not in CITY_LOADERS:
        raise HTTPException(404, f"Ciudad '{city}' no disponible. Opciones: {list(CITY_LOADERS)}")

    data = CITY_LOADERS[city]()
    if data is None:
        raise HTTPException(503, f"Datos de {city} no disponibles aún")

    features = data["features"]

    if quintil is not None:
        features = [f for f in features if f["properties"].get("alpha_quintil") == quintil]
    if min_score is not None:
        features = [f for f in features if (f["properties"].get("alpha_score") or 0) >= min_score]
    if max_score is not None:
        features = [f for f in features if (f["properties"].get("alpha_score") or 0) <= max_score]

    features = features[:limit]

    stats = CITY_STATS[city]()
    stats["city"] = city

    if geojson:
        return {
            "type": "FeatureCollection",
            "properties": {"city": city, "count": len(features), "stats": stats},
            "features": features,
        }
    else:
        return {
            "city": city,
            "count": len(features),
            "stats": stats,
            "radios": [f["properties"] for f in features],
        }


@router.get("/{city}/stats")
def get_city_stats(city: str) -> Any:
    if city not in CITY_STATS:
        raise HTTPException(404, f"Ciudad '{city}' no disponible")
    stats = CITY_STATS[city]()
    if not stats:
        raise HTTPException(503, f"Datos de {city} no disponibles")
    stats["city"] = city
    return stats


@router.get("/{city}/top")
def get_top_radios(
    city: str,
    n: int = Query(10, ge=1, le=100),
) -> Any:
    if city not in CITY_LOADERS:
        raise HTTPException(404, f"Ciudad '{city}' no disponible")
    data = CITY_LOADERS[city]()
    if data is None:
        raise HTTPException(503, f"Datos de {city} no disponibles")

    features = sorted(
        data["features"],
        key=lambda f: f["properties"].get("alpha_score") or 0,
        reverse=True,
    )[:n]

    return {"city": city, "top": [f["properties"] for f in features]}
