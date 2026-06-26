from typing import Any
from fastapi import APIRouter, HTTPException
from ..data_loader import get_caba_geojson, get_gba_geojson

router = APIRouter(prefix="/radios", tags=["radios"])

_ALL_LOADERS = [
    ("caba", get_caba_geojson),
    ("gba",  get_gba_geojson),
]


@router.get("/{link}")
def get_radio_detail(link: str) -> Any:
    for city, loader in _ALL_LOADERS:
        data = loader()
        if data is None:
            continue
        for f in data["features"]:
            if f["properties"].get("link") == link:
                return {
                    "link": link,
                    "city": city,
                    "geometry": f.get("geometry"),
                    "properties": f["properties"],
                }
    raise HTTPException(404, f"Radio '{link}' no encontrado")
