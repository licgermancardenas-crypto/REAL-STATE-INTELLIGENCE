"""
Recorta los POIs de Overpass al polígono real de un barrio (no al bbox).

Problema: Overpass devuelve todo lo que cae dentro del rectángulo bbox, que
incluye elementos de barrios vecinos. Este script hace el clip preciso contra
el polígono oficial del barrio (GCBA CDN).

Coordenadas:
  - Nodos Overpass: lat/lon en la raíz del elemento.
  - Ways/relations con "out center": lat/lon bajo la clave "center".
  Ambos casos son manejados por _to_geodataframe().

Uso:
  python src/utils/clip_pois.py                     # Palermo, todas las cats
  python src/utils/clip_pois.py Belgrano            # otro barrio (si hay datos)
  python src/utils/clip_pois.py Palermo salud       # una sola categoría
"""
import json
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
from loguru import logger

# Paths relativos a la raíz del proyecto
ROOT = Path(__file__).parent.parent.parent
DATA_RAW       = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"

BARRIOS_GEOJSON = DATA_RAW / "gcba" / "barrios_caba.geojson"


def load_barrio_polygon(nombre: str) -> gpd.GeoDataFrame:
    """Carga el polígono del barrio desde el GeoJSON oficial GCBA."""
    gdf = gpd.read_file(BARRIOS_GEOJSON)
    match = gdf[gdf["nombre"].str.lower() == nombre.lower()]
    if match.empty:
        available = sorted(gdf["nombre"].tolist())
        raise ValueError(
            f"Barrio '{nombre}' no encontrado. Disponibles: {available}"
        )
    return match.to_crs(epsg=4326)


def _to_geodataframe(elements: list[dict]) -> gpd.GeoDataFrame:
    """
    Convierte lista de elementos Overpass a GeoDataFrame de puntos.
    Maneja dos formatos:
      - Nodos: {"lat": ..., "lon": ...}  en la raíz
      - Ways/relations con out center: {"center": {"lat": ..., "lon": ...}}
    Elementos sin coordenadas se descartan.
    """
    rows = []
    skipped = 0
    for elem in elements:
        lat = elem.get("lat")
        lon = elem.get("lon")
        if lat is None and "center" in elem and elem["center"]:
            lat = elem["center"].get("lat")
            lon = elem["center"].get("lon")
        if lat is None or lon is None:
            skipped += 1
            continue
        rows.append({
            "osm_id":   elem.get("id"),
            "osm_type": elem.get("type"),
            "lat":      float(lat),
            "lon":      float(lon),
            **{f"tag_{k}": v for k, v in (elem.get("tags") or {}).items()},
        })
    if skipped:
        logger.debug(f"  {skipped} elementos sin coordenadas descartados")
    if not rows:
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    df = pd.DataFrame(rows)
    return gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df["lon"], df["lat"]),
        crs="EPSG:4326",
    )


def clip_pois(
    barrio: str,
    osm_dir: Path,
    categories: list[str] | None = None,
) -> dict[str, dict]:
    """
    Carga los JSONs de Overpass en osm_dir, recorta al polígono de barrio,
    guarda en data/processed/osm/<ciudad_barrio>_clean/.

    Devuelve dict por categoría con {"antes": n, "despues": m, "reduccion_pct": x}.
    """
    poly = load_barrio_polygon(barrio)
    logger.info(f"Polígono '{barrio}' cargado — área: {poly.geometry.iloc[0].area:.6f}°²")

    json_files = sorted(osm_dir.glob("*.json"))
    if categories:
        json_files = [f for f in json_files if f.stem in categories]

    if not json_files:
        logger.warning(f"No se encontraron JSONs en {osm_dir}")
        return {}

    ciudad_id = osm_dir.name  # ej: "caba_palermo"
    out_dir = DATA_PROCESSED / "osm" / f"{ciudad_id}_clean"
    out_dir.mkdir(parents=True, exist_ok=True)

    report: dict[str, dict] = {}

    for json_path in json_files:
        cat = json_path.stem
        elements = json.loads(json_path.read_text(encoding="utf-8")).get("elements", [])
        n_antes = len(elements)

        gdf = _to_geodataframe(elements)
        if gdf.empty:
            logger.warning(f"  {cat}: sin geometrías válidas")
            report[cat] = {"antes": n_antes, "despues": 0, "reduccion_pct": 100.0}
            continue

        # sjoin within: conserva solo los puntos que caen DENTRO del polígono
        clipped = gpd.sjoin(gdf, poly[["geometry"]], how="inner", predicate="within")
        clipped = clipped.drop(columns=["index_right"], errors="ignore")
        n_despues = len(clipped)

        pct = round((n_antes - n_despues) / n_antes * 100, 1) if n_antes else 0.0
        report[cat] = {"antes": n_antes, "despues": n_despues, "reduccion_pct": pct}

        # Guardar como GeoPackage
        out_path = out_dir / f"{cat}.gpkg"
        clipped.to_file(out_path, driver="GPKG")
        logger.info(
            f"  {cat}: {n_antes} → {n_despues} POIs "
            f"(-{pct}%) → {out_path.name}"
        )

    logger.info(f"\nClip completo. Archivos limpios → {out_dir}")
    return report


def print_report(report: dict[str, dict]) -> None:
    sep = "-" * 52
    print("\n" + sep)
    print(f"{'Categoria':<20} {'Antes':>7} {'Despues':>8} {'Reduccion':>10}")
    print(sep)
    total_antes = total_despues = 0
    for cat, d in sorted(report.items()):
        print(f"{cat:<20} {d['antes']:>7} {d['despues']:>8} {d['reduccion_pct']:>9.1f}%")
        total_antes    += d["antes"]
        total_despues  += d["despues"]
    print(sep)
    total_pct = round((total_antes - total_despues) / total_antes * 100, 1) if total_antes else 0.0
    print(f"{'TOTAL':<20} {total_antes:>7} {total_despues:>8} {total_pct:>9.1f}%")
    print(sep)


if __name__ == "__main__":
    args = sys.argv[1:]
    barrio = args[0] if args else "Palermo"
    cats   = args[1:] if len(args) > 1 else None

    ciudad_id = f"caba_{barrio.lower().replace(' ', '_')}"
    osm_dir   = DATA_RAW / "osm" / ciudad_id

    if not osm_dir.exists():
        logger.error(f"Directorio no encontrado: {osm_dir}")
        logger.error("Corré primero: python src/ingesta/overpass.py")
        sys.exit(1)

    report = clip_pois(barrio, osm_dir, categories=cats)
    print_report(report)
