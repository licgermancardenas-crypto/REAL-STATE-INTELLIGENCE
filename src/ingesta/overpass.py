"""
Overpass API (OSM) — POIs para análisis de accesibilidad urbana.
Sin autenticación. Rate limit: usar con pauses entre queries.
"""
import json
import time
import httpx
from loguru import logger
from config import OVERPASS_URL, OVERPASS_FALLBACK, DATA_RAW

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
            resp = None
            for endpoint in (OVERPASS_URL, OVERPASS_FALLBACK):
                resp = httpx.post(
                    endpoint,
                    data={"data": query},
                    headers={"Accept": "*/*", "Content-Type": "application/x-www-form-urlencoded"},
                    timeout=90,
                )
                if resp.status_code == 200:
                    break
                logger.warning(f"  {endpoint} → {resp.status_code}, probando fallback...")
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


def bbox_from_georef(barrio: str, offset_deg: float = 0.025) -> tuple[float, float, float, float] | None:
    """
    Lee data/raw/georef/barrios_caba.json y genera un bbox cuadrado
    centrado en el centroide del barrio pedido.
    offset_deg: radio en grados (~2.5km por defecto).
    """
    import json as _json
    path = DATA_RAW / "georef" / "barrios_caba.json"
    if not path.exists():
        logger.warning(f"GeoRef JSON no encontrado: {path} — corré primero georef.py")
        return None
    data = _json.loads(path.read_text(encoding="utf-8"))
    for item in data.get("localidades", []):
        if item["nombre"].lower() == barrio.lower():
            lat = item["centroide"]["lat"]
            lon = item["centroide"]["lon"]
            bbox = (lon - offset_deg, lat - offset_deg, lon + offset_deg, lat + offset_deg)
            logger.info(f"Bbox '{barrio}' desde GeoRef: {bbox}")
            return bbox
    logger.warning(f"Barrio '{barrio}' no encontrado en GeoRef JSON")
    return None


if __name__ == "__main__":
    import sys
    barrio = sys.argv[1] if len(sys.argv) > 1 else "Palermo"
    ciudad_id = f"caba_{barrio.lower().replace(' ', '_')}"

    bbox = bbox_from_georef(barrio)
    if bbox is None:
        # fallback hardcodeado solo si GeoRef no está disponible
        logger.warning("Usando bbox hardcodeado de fallback")
        bbox = (-58.4460, -34.6062, -58.3960, -34.5562)  # Palermo centroid ± 0.025°

    save_pois(ciudad_id, bbox, categories=["educacion", "transporte", "espacios_verdes"])
