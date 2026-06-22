"""
Overpass API (OSM) — POIs para análisis de accesibilidad urbana.
Sin autenticación. Rate limit: usar con pauses entre queries.
"""
import json
import time
import httpx
from loguru import logger
from config import OVERPASS_URL, DATA_RAW

POI_CATEGORIES = {
    "educacion": [
        '["amenity"="university"]',
        '["amenity"="school"]',
        '["amenity"="college"]',
    ],
    "salud": [
        '["amenity"="hospital"]',
        '["amenity"="clinic"]',
        '["amenity"="pharmacy"]',
    ],
    "transporte": [
        '["public_transport"="stop_position"]',
        '["highway"="bus_stop"]',
        '["railway"="station"]',
        '["railway"="subway_entrance"]',
    ],
    "comercio": [
        '["shop"~"supermarket|mall|department_store"]',
        '["amenity"="marketplace"]',
    ],
    "oficinas": [
        '["office"]',
        '["building"="office"]',
    ],
    "espacios_verdes": [
        '["leisure"="park"]',
        '["landuse"="recreation_ground"]',
    ],
}


def _build_query(bbox: tuple[float, float, float, float], filters: list[str]) -> str:
    s, w, n, e = bbox[1], bbox[0], bbox[3], bbox[2]
    bbox_str = f"{s},{w},{n},{e}"
    nodes = "\n".join(f'  node{f}({bbox_str});' for f in filters)
    ways = "\n".join(f'  way{f}({bbox_str});' for f in filters)
    return f"[out:json][timeout:60];\n(\n{nodes}\n{ways}\n);\nout center;"


def fetch_pois(
    bbox: tuple[float, float, float, float],
    categories: list[str] | None = None,
) -> dict[str, list[dict]]:
    """
    Descarga POIs OSM para un bbox dado.
    bbox: (lon_min, lat_min, lon_max, lat_max)
    categories: subconjunto de POI_CATEGORIES; None = todas
    """
    cats = categories or list(POI_CATEGORIES.keys())
    results: dict[str, list[dict]] = {}

    for cat in cats:
        filters = POI_CATEGORIES[cat]
        query = _build_query(bbox, filters)
        logger.info(f"Overpass: fetching {cat} ...")
        try:
            resp = httpx.post(OVERPASS_URL, data={"data": query}, timeout=90)
            resp.raise_for_status()
            elements = resp.json().get("elements", [])
            results[cat] = elements
            logger.info(f"  {cat}: {len(elements)} elementos")
        except Exception as e:
            logger.warning(f"  {cat} falló: {e}")
            results[cat] = []
        time.sleep(3)

    return results


def save_pois(ciudad_id: str, bbox: tuple, categories: list[str] | None = None) -> None:
    pois = fetch_pois(bbox, categories)
    out = DATA_RAW / "osm" / ciudad_id
    out.mkdir(parents=True, exist_ok=True)
    for cat, elements in pois.items():
        path = out / f"{cat}.json"
        path.write_text(json.dumps({"elements": elements}, ensure_ascii=False), encoding="utf-8")
    logger.info(f"POIs guardados → {out}")


if __name__ == "__main__":
    # Piloto: Palermo bbox aproximado
    PALERMO_BBOX = (-58.4415, -34.5960, -58.4035, -34.5700)
    from config import CIUDADES
    save_pois("caba_palermo", PALERMO_BBOX, categories=["educacion", "transporte", "espacios_verdes"])
