"""
Overpass API (OSM) — POIs para análisis de accesibilidad urbana.

CADENA DE FALLBACKS (en orden):
  1. overpass-api.de           Instancia canónica (Roland Olbricht, autor del software).
                               Es la fuente de referencia, pero puede bloquear IPs por
                               rate-limit o tráfico inesperado (devuelve 406).
  2. overpass.kumi.systems     Mirror comunitario europeo. Mismo software, datos OSM
                               sincronizados. Alternativa neutral cuando cae la canónica.
  3. maps.mail.ru/osm/...      Instancia operada por VK/Mail.ru. Funcionó en pruebas desde
                               esta red cuando los anteriores fallaron. Consideración: es
                               infraestructura de una empresa rusa.
  4. ohsome API (HeiGIT)       API de HeiGIT (Heidelberg Institute for Geoinformation
                               Technology). Formato completamente distinto a Overpass
                               (GeoJSON centroid + filter syntax propio), por eso va último
                               — requiere un adaptador y la respuesta se convierte al
                               formato interno de elementos Overpass.

Los tres primeros reciben la misma OverpassQL query via POST form-encoded.
El cuarto usa su propio adaptador (_fetch_ohsome) y solo se activa si los tres
anteriores fallan. El resultado final es siempre el mismo: lista de elementos
con {type, lat, lon, tags}.
"""
import json
import re
import time
import httpx
from loguru import logger
from config import OVERPASS_ENDPOINTS, OHSOME_BASE, DATA_RAW

# Snapshot date para ohsome — datos OSM a esta fecha
_OHSOME_TIME = "2025-01-01"

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

# Equivalentes en sintaxis ohsome para cada categoría.
# ohsome usa "key=value" y operadores "in", "or", "*" — diferente a OverpassQL.
_OHSOME_FILTERS: dict[str, str] = {
    "educacion":      "amenity in (university, school, college)",
    "salud":          "amenity in (hospital, clinic, pharmacy)",
    "transporte":     "public_transport=stop_position or highway=bus_stop or railway in (station, subway_entrance)",
    "comercio":       "shop in (supermarket, mall, department_store) or amenity=marketplace",
    "oficinas":       "office=* or building=office",
    "espacios_verdes":"leisure=park or landuse=recreation_ground",
}


def _build_overpass_query(bbox: tuple[float, float, float, float], filters: list[str]) -> str:
    """Construye una OverpassQL query para los tres primeros endpoints."""
    s, w, n, e = bbox[1], bbox[0], bbox[3], bbox[2]
    bbox_str = f"{s},{w},{n},{e}"
    nodes = "\n".join(f'  node{f}({bbox_str});' for f in filters)
    ways  = "\n".join(f'  way{f}({bbox_str});'  for f in filters)
    return f"[out:json][timeout:60];\n(\n{nodes}\n{ways}\n);\nout center;"


def _fetch_overpass(query: str) -> list[dict] | None:
    """
    Intenta los tres endpoints Overpass en orden.
    Devuelve la lista de elementos si alguno responde 200, None si todos fallan.
    """
    headers = {
        "Accept": "*/*",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    for i, endpoint in enumerate(OVERPASS_ENDPOINTS):
        # overpass-api.de devuelve 406 al instante (IP bloqueada).
        # kumi.systems tarda consistentemente >5s antes de agotar el timeout.
        # 5s es suficiente para detectar un mirror sano; el último (maps.mail.ru)
        # recibe 90s porque es el que funciona y procesa queries grandes.
        timeout = 90 if i == len(OVERPASS_ENDPOINTS) - 1 else 5
        try:
            resp = httpx.post(endpoint, data={"data": query}, headers=headers, timeout=timeout)
            if resp.status_code == 200:
                logger.debug(f"  Overpass OK: {endpoint}")
                return resp.json().get("elements", [])
            logger.warning(f"  {endpoint} → {resp.status_code}")
        except Exception as e:
            logger.warning(f"  {endpoint} → error: {e}")
    return None


def _fetch_ohsome(bbox: tuple[float, float, float, float], category: str) -> list[dict] | None:
    """
    Adaptador ohsome API — último fallback.

    Endpoint: POST https://api.ohsome.org/v1/elements/centroid
    Parámetros (form data):
      bboxes: lon_min,lat_min,lon_max,lat_max  (mismo orden que nuestro bbox)
      filter: expresión ohsome (sintaxis distinta a OverpassQL)
      time:   fecha snapshot ISO

    La respuesta es un GeoJSON FeatureCollection. Se convierte al formato
    interno de elementos Overpass: {type, id, lat, lon, tags}.
    """
    ohsome_filter = _OHSOME_FILTERS.get(category)
    if not ohsome_filter:
        logger.warning(f"ohsome: no hay filtro definido para categoría '{category}'")
        return None

    lon_min, lat_min, lon_max, lat_max = bbox
    url = f"{OHSOME_BASE}/elements/centroid"
    data = {
        "bboxes": f"{lon_min},{lat_min},{lon_max},{lat_max}",
        "filter": ohsome_filter,
        "time": _OHSOME_TIME,
    }

    try:
        resp = httpx.post(url, data=data, timeout=120)
        if resp.status_code != 200:
            logger.warning(f"  ohsome → {resp.status_code}: {resp.text[:200]}")
            return None

        geojson = resp.json()
        features = geojson.get("features", [])

        # Convertir GeoJSON Features → formato Overpass elements
        elements = []
        for feat in features:
            coords = feat.get("geometry", {}).get("coordinates", [None, None])
            props  = feat.get("properties", {})
            osm_id_str = props.get("@osmId", "")          # ej: "node/123456"
            osm_type   = osm_id_str.split("/")[0] if "/" in osm_id_str else "node"
            osm_id     = int(osm_id_str.split("/")[1]) if "/" in osm_id_str else 0
            tags       = {k: v for k, v in props.items() if not k.startswith("@")}
            if coords[0] is not None:
                elements.append({
                    "type": osm_type,
                    "id":   osm_id,
                    "lon":  coords[0],
                    "lat":  coords[1],
                    "tags": tags,
                })

        logger.debug(f"  ohsome OK: {len(elements)} elementos para '{category}'")
        return elements

    except Exception as e:
        logger.warning(f"  ohsome → error: {e}")
        return None


def fetch_pois(
    bbox: tuple[float, float, float, float],
    categories: list[str] | None = None,
) -> dict[str, list[dict]]:
    """
    Descarga POIs OSM para un bbox dado usando la cadena de fallbacks.
    bbox: (lon_min, lat_min, lon_max, lat_max)
    categories: subconjunto de POI_CATEGORIES; None = todas.
    """
    cats = categories or list(POI_CATEGORIES.keys())
    results: dict[str, list[dict]] = {}

    for cat in cats:
        logger.info(f"Fetching POIs: {cat} ...")

        # Intentar los 3 endpoints Overpass
        query = _build_overpass_query(bbox, POI_CATEGORIES[cat])
        elements = _fetch_overpass(query)

        # Si todos los Overpass fallaron, intentar ohsome
        if elements is None:
            logger.warning(f"  Todos los endpoints Overpass fallaron para '{cat}'. Usando ohsome ...")
            elements = _fetch_ohsome(bbox, cat)

        if elements is None:
            logger.error(f"  '{cat}': fallaron los 4 endpoints. Dejando vacío.")
            elements = []

        results[cat] = elements
        logger.info(f"  {cat}: {len(elements)} elementos")
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
    offset_deg: radio en grados (~2.5 km por defecto).
    """
    path = DATA_RAW / "georef" / "barrios_caba.json"
    if not path.exists():
        logger.warning(f"GeoRef JSON no encontrado: {path} — corré primero georef.py")
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
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
    args = sys.argv[1:]

    # Si todos los args son categorías conocidas → usarlas con barrio default Palermo.
    # Si el primer arg no es categoría → es el nombre del barrio; el resto son categorías.
    known_cats = set(POI_CATEGORIES.keys())
    if args and args[0] in known_cats:
        barrio = "Palermo"
        cats = args
    elif args:
        barrio = args[0]
        cats = args[1:] if len(args) > 1 else None  # None = todas
    else:
        barrio = "Palermo"
        cats = None

    ciudad_id = f"caba_{barrio.lower().replace(' ', '_')}"

    bbox = bbox_from_georef(barrio)
    if bbox is None:
        logger.warning("Usando bbox hardcodeado de fallback")
        bbox = (-58.4460, -34.6062, -58.3960, -34.5562)  # Palermo centroid ± 0.025°

    save_pois(ciudad_id, bbox, categories=cats)
