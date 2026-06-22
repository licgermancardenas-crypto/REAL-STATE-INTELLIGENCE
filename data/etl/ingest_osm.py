"""
Ingesta OSM via Overpass API.
Extrae: calles, POIs (comercios, transporte, servicios), espacios verdes.
Output: GeoJSON por ciudad en data/raw/osm/{city_id}/
"""
import json
import time
from pathlib import Path

import httpx
from loguru import logger

from config import CITIES, OVERPASS_URL, RAW_DIR

POI_QUERY = """
[out:json][timeout:60];
area({area_id})->.searchArea;
(
  node["amenity"](area.searchArea);
  node["shop"](area.searchArea);
  node["public_transport"](area.searchArea);
  node["leisure"="park"](area.searchArea);
);
out body;
"""

STREETS_QUERY = """
[out:json][timeout:60];
area({area_id})->.searchArea;
way["highway"~"primary|secondary|tertiary|residential"](area.searchArea);
out geom;
"""


def fetch_overpass(query: str) -> dict:
    resp = httpx.post(OVERPASS_URL, data={"data": query}, timeout=90)
    resp.raise_for_status()
    return resp.json()


def ingest_city(city_id: str) -> None:
    city = CITIES[city_id]
    out_dir = RAW_DIR / "osm" / city_id
    out_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Ingesting OSM POIs for {city['name']}")
    pois = fetch_overpass(POI_QUERY.format(area_id=city["osm_area_id"]))
    (out_dir / "pois.json").write_text(json.dumps(pois, ensure_ascii=False), encoding="utf-8")
    logger.info(f"  POIs: {len(pois.get('elements', []))} nodes")

    time.sleep(5)  # Overpass rate limit

    logger.info(f"Ingesting OSM streets for {city['name']}")
    streets = fetch_overpass(STREETS_QUERY.format(area_id=city["osm_area_id"]))
    (out_dir / "streets.json").write_text(json.dumps(streets, ensure_ascii=False), encoding="utf-8")
    logger.info(f"  Streets: {len(streets.get('elements', []))} ways")


if __name__ == "__main__":
    import sys
    city_id = sys.argv[1] if len(sys.argv) > 1 else "caba"
    ingest_city(city_id)
