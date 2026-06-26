"""
Genera las capas auxiliares del mapa Gap de Valor:
  1. apps/web/public/comunas_caba.geojson  — 15 polígonos disueltos
  2. apps/web/public/subte_lines_caba.geojson — rutas de subte (Overpass OSM)
  3. apps/web/public/subte_stations_caba.geojson — estaciones (Overpass OSM)
"""
import json
import time
import urllib.request
import urllib.parse
from pathlib import Path

ROOT   = Path(__file__).parent.parent
PUBLIC = ROOT / "apps/web/public"
PUBLIC.mkdir(parents=True, exist_ok=True)

# ── 1. Comunas — dissolve barrios by `comuna` field ──────────────────────────

def gen_comunas():
    try:
        import geopandas as gpd
    except ImportError:
        print("geopandas requerido para comunas. Instalalo con: pip install geopandas")
        return False

    geo_src = ROOT / "data/raw/geo/barrios_gcba.geojson"
    gdf = gpd.read_file(geo_src)
    gdf["comuna"] = gdf["comuna"].astype(int)
    comunas = gdf.dissolve(by="comuna", as_index=False)[["comuna", "geometry"]]
    comunas["id"] = comunas["comuna"].apply(lambda c: f"Comuna {c}")

    out = PUBLIC / "comunas_caba.geojson"
    comunas.to_file(out, driver="GeoJSON")
    # Rewrite compact (geopandas writes pretty-printed)
    d = json.loads(out.read_text(encoding="utf-8"))
    out.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"OK comunas_caba.geojson — {len(comunas)} comunas")
    return True


# ── 2 + 3. Subte lines + stations via Overpass OSM ───────────────────────────

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Official SBASE colours keyed by the route_ref tag (line letter)
LINE_COLORS = {
    "A": "#E4002B",
    "B": "#E4002B",   # shown as distinct label even if same colour family
    "C": "#0050A0",
    "D": "#00843D",
    "E": "#7B2D8B",
    "H": "#FFB81C",
    "P": "#00A3A0",   # PreMetro
}

def overpass(query: str) -> dict:
    data = urllib.parse.urlencode({"data": query}).encode()
    req  = urllib.request.Request(OVERPASS_URL, data=data,
                                  headers={"User-Agent": "RSI-PropTech/1.0"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read().decode("utf-8"))


def gen_subte():
    # ── Lines ────────────────────────────────────────────────────────────────
    q_lines = """
[out:json][timeout:60];
relation["route"="subway"]["network"~"Subte|SBASE|Buenos Aires",i];
out geom;
"""
    print("Consultando líneas de subte en Overpass…")
    raw_lines = overpass(q_lines)

    line_features = []
    for el in raw_lines.get("elements", []):
        if el["type"] != "relation":
            continue
        tags    = el.get("tags", {})
        ref     = tags.get("route_ref") or tags.get("ref") or tags.get("name", "?")
        # extract single letter from e.g. "Línea A", "A", "subteA"
        import re
        m = re.search(r'\b([A-HP])\b', ref, re.IGNORECASE)
        letter  = m.group(1).upper() if m else ref[:1].upper()
        colour  = tags.get("colour") or LINE_COLORS.get(letter, "#888888")
        name    = tags.get("name") or f"Línea {letter}"

        # Collect all way members as LineString coordinates
        for member in el.get("members", []):
            if member.get("type") != "way":
                continue
            geom = member.get("geometry", [])
            if len(geom) < 2:
                continue
            coords = [[g["lon"], g["lat"]] for g in geom]
            line_features.append({
                "type": "Feature",
                "properties": {
                    "linea":  letter,
                    "nombre": name,
                    "colour": colour,
                },
                "geometry": {"type": "LineString", "coordinates": coords},
            })

    out_lines = PUBLIC / "subte_lines_caba.geojson"
    out_lines.write_text(
        json.dumps({"type": "FeatureCollection", "features": line_features},
                   ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8"
    )
    print(f"OK subte_lines_caba.geojson — {len(line_features)} segmentos")

    time.sleep(2)   # be polite to Overpass

    # ── Stations ─────────────────────────────────────────────────────────────
    q_stations = """
[out:json][timeout:60];
(
  node["station"="subway"]["network"~"Subte|SBASE|Buenos Aires",i];
  node["railway"="station"]["network"~"Subte|SBASE|Buenos Aires",i];
);
out body;
"""
    print("Consultando estaciones de subte en Overpass…")
    raw_stations = overpass(q_stations)

    seen_names = set()
    station_features = []
    for el in raw_stations.get("elements", []):
        if el["type"] != "node":
            continue
        tags = el.get("tags", {})
        name = tags.get("name") or tags.get("official_name", "")
        if not name or name in seen_names:
            continue
        seen_names.add(name)

        ref    = tags.get("route_ref") or tags.get("line") or ""
        import re
        m = re.search(r'\b([A-HP])\b', ref, re.IGNORECASE)
        letter = m.group(1).upper() if m else ""
        colour = LINE_COLORS.get(letter, "#888888")

        station_features.append({
            "type": "Feature",
            "properties": {
                "name":   name,
                "linea":  letter,
                "colour": colour,
            },
            "geometry": {"type": "Point",
                         "coordinates": [el["lon"], el["lat"]]},
        })

    out_stations = PUBLIC / "subte_stations_caba.geojson"
    out_stations.write_text(
        json.dumps({"type": "FeatureCollection", "features": station_features},
                   ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8"
    )
    print(f"OK subte_stations_caba.geojson — {len(station_features)} estaciones")


if __name__ == "__main__":
    gen_comunas()
    gen_subte()
    print("Listo.")
