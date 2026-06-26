"""
Pipeline completo GBA — descarga POIs OSM + clip a radios por partido.

Proceso por cada partido (depto) dentro del Conurbano Bonaerense:
  1. Calcula bbox del partido a partir de pba_radios.gpkg
  2. Llama a overpass.save_pois() → data/raw/osm/gba_{depto}/
  3. Clipea POIs al polígono del partido (unión de sus radios)
  4. Guarda data/processed/osm/gba_{depto}_clean/{cat}.gpkg

Partidos seleccionados: todos los depto_codes con >= MIN_RADIOS radios
dentro del Conurbano bbox.

Uso:
  python src/pipeline/gba_full.py            # todos los partidos
  python src/pipeline/gba_full.py 427        # solo depto 427 (La Matanza)
  python src/pipeline/gba_full.py skip       # salta descarga, solo clip
"""
import json
import sys
import time
from pathlib import Path

import geopandas as gpd
import pandas as pd
from loguru import logger
from shapely.geometry import Point

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "ingesta"))  # para overpass.py → from config import

from ingesta.overpass import save_pois, POI_CATEGORIES

DATA_RAW       = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"

# Conurbano Bonaerense bbox
CONURBANO_BBOX = (-59.1, -35.1, -58.2, -34.3)

# Solo partidos con suficientes radios (filtra municipios periféricos)
MIN_RADIOS = 50

# Buffer (grados) alrededor del bbox de cada partido para Overpass
BBOX_BUFFER = 0.01


def get_conurbano_deptos(
    radios_path: Path,
    bbox: tuple[float, float, float, float],
    min_radios: int,
) -> dict[str, dict]:
    """
    Devuelve {depto_code: {"n_radios": int, "bbox": (lon_min, lat_min, lon_max, lat_max)}}
    para los partidos del Conurbano con >= min_radios radios.
    """
    pba = gpd.read_file(radios_path).to_crs("EPSG:4326")
    lon_min, lat_min, lon_max, lat_max = bbox

    cx = pba.geometry.centroid.x
    cy = pba.geometry.centroid.y
    mask = (cx >= lon_min) & (cx <= lon_max) & (cy >= lat_min) & (cy <= lat_max)
    conurbano = pba[mask].copy()
    conurbano["depto_code"] = conurbano["link"].str[2:5]

    result = {}
    for depto, group in conurbano.groupby("depto_code"):
        if len(group) < min_radios:
            continue
        bounds = group.geometry.total_bounds  # (minx, miny, maxx, maxy)
        result[depto] = {
            "n_radios": len(group),
            "bbox": (
                bounds[0] - BBOX_BUFFER,
                bounds[1] - BBOX_BUFFER,
                bounds[2] + BBOX_BUFFER,
                bounds[3] + BBOX_BUFFER,
            ),
        }
    return result


def _get_depto_polygon(
    radios_path: Path,
    depto_code: str,
    conurbano_bbox: tuple,
) -> gpd.GeoDataFrame:
    """Unión de todos los radios de un depto dentro del Conurbano."""
    pba = gpd.read_file(radios_path).to_crs("EPSG:4326")
    lon_min, lat_min, lon_max, lat_max = conurbano_bbox
    cx = pba.geometry.centroid.x
    cy = pba.geometry.centroid.y
    bbox_mask = (cx >= lon_min) & (cx <= lon_max) & (cy >= lat_min) & (cy <= lat_max)
    depto_mask = pba["link"].str[2:5] == depto_code
    subset = pba[bbox_mask & depto_mask]
    union = subset.geometry.union_all()
    return gpd.GeoDataFrame(geometry=[union], crs="EPSG:4326")


def _to_geodataframe(elements: list[dict]) -> gpd.GeoDataFrame:
    """Convierte elementos Overpass a GeoDataFrame de puntos."""
    rows = []
    for elem in elements:
        lat = elem.get("lat")
        lon = elem.get("lon")
        if lat is None and "center" in elem and elem["center"]:
            lat = elem["center"].get("lat")
            lon = elem["center"].get("lon")
        if lat is None or lon is None:
            continue
        rows.append({
            "osm_id":   elem.get("id"),
            "osm_type": elem.get("type"),
            "lat":      float(lat),
            "lon":      float(lon),
            **{f"tag_{k}": v for k, v in (elem.get("tags") or {}).items()},
        })
    if not rows:
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    df = pd.DataFrame(rows)
    return gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df["lon"], df["lat"]),
        crs="EPSG:4326",
    )


def clip_depto_pois(
    depto_code: str,
    depto_poly: gpd.GeoDataFrame,
    raw_dir: Path,
    out_dir: Path,
) -> dict:
    """
    Lee JSONs de Overpass en raw_dir, clipea al polígono del depto,
    guarda GPKGs en out_dir.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    report = {}

    for json_path in sorted(raw_dir.glob("*.json")):
        cat = json_path.stem
        elements = json.loads(json_path.read_text(encoding="utf-8")).get("elements", [])
        n_antes = len(elements)

        gdf = _to_geodataframe(elements)
        if gdf.empty:
            out_path = out_dir / f"{cat}.gpkg"
            gpd.GeoDataFrame(geometry=[], crs="EPSG:4326").to_file(out_path, driver="GPKG")
            report[cat] = {"antes": n_antes, "despues": 0}
            continue

        clipped = gpd.sjoin(gdf, depto_poly[["geometry"]], how="inner", predicate="within")
        clipped = clipped.drop(columns=["index_right"], errors="ignore")
        n_despues = len(clipped)

        out_path = out_dir / f"{cat}.gpkg"
        clipped.to_file(out_path, driver="GPKG")
        report[cat] = {"antes": n_antes, "despues": n_despues}
        pct = (n_antes - n_despues) / n_antes * 100 if n_antes else 0
        logger.info(f"  {cat}: {n_antes} → {n_despues} (-{pct:.0f}%)")

    return report


def run(
    target_deptos: list[str] | None = None,
    skip_download: bool = False,
) -> None:
    radios_path = DATA_PROCESSED / "census" / "pba_radios.gpkg"

    logger.info("=== GBA Full Pipeline ===")
    deptos = get_conurbano_deptos(radios_path, CONURBANO_BBOX, MIN_RADIOS)
    logger.info(f"Partidos del Conurbano (>= {MIN_RADIOS} radios): {len(deptos)}")
    for code, info in sorted(deptos.items(), key=lambda x: -x[1]["n_radios"]):
        logger.info(f"  {code}: {info['n_radios']} radios")

    if target_deptos:
        deptos = {k: v for k, v in deptos.items() if k in target_deptos}
        logger.info(f"Filtrando a: {list(deptos.keys())}")

    total_cats = len(POI_CATEGORIES)
    total_queries = len(deptos) * total_cats
    logger.info(f"Total queries Overpass: {len(deptos)} partidos × {total_cats} cats = {total_queries}")

    cats = list(POI_CATEGORIES.keys())

    for i, (depto, info) in enumerate(sorted(deptos.items()), 1):
        ciudad_id = f"gba_{depto}"
        raw_dir   = DATA_RAW / "osm" / ciudad_id
        clean_dir = DATA_PROCESSED / "osm" / f"{ciudad_id}_clean"

        logger.info(f"\n[{i}/{len(deptos)}] Partido {depto} — {info['n_radios']} radios")

        if not skip_download:
            # Verificar qué categorías ya tienen datos (cache)
            pending_cats = []
            for cat in cats:
                json_path = raw_dir / f"{cat}.json"
                if json_path.exists():
                    logger.info(f"  Cache hit: {cat} ({json_path.stat().st_size / 1024:.0f} KB)")
                else:
                    pending_cats.append(cat)

            if pending_cats:
                logger.info(f"  Descargando {len(pending_cats)} categorías ...")
                try:
                    save_pois(ciudad_id, info["bbox"], categories=pending_cats)
                except Exception as e:
                    logger.error(f"  ERROR descarga {depto}: {e}")
                    continue
            else:
                logger.info(f"  Todas las categorías en cache.")

        # Clip a polígono del depto
        if not raw_dir.exists():
            logger.warning(f"  {raw_dir} no existe — saltando clip")
            continue

        depto_poly = _get_depto_polygon(radios_path, depto, CONURBANO_BBOX)
        logger.info(f"  Clipeando a polígono del partido ...")
        clip_depto_pois(depto, depto_poly, raw_dir, clean_dir)

    logger.info("\n=== GBA Full Pipeline completado ===")
    n_processed = sum(
        1 for code in deptos
        if (DATA_PROCESSED / "osm" / f"gba_{code}_clean").exists()
    )
    logger.info(f"Partidos procesados: {n_processed}/{len(deptos)}")


if __name__ == "__main__":
    args = sys.argv[1:]
    skip = "skip" in args
    target = [a for a in args if a != "skip" and len(a) == 3]
    run(target_deptos=target or None, skip_download=skip)
