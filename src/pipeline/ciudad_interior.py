"""
Pipeline ciudades interiores — Alpha Score para Rosario, Córdoba, Mendoza (y cualquier ciudad ARG).

Modo PARCIAL (inmediato, sin POIs):
  Requiere solo data/raw/indec/radios_censales.gpkg
  3 variables censales: densidad_pob (50%), hogares_tot (30%), tasa_ocup (20%)
  → Score comparable con GBA parcial, NO con CABA (8 vars)

Modo COMPLETO (requiere correr Overpass previamente):
  7 variables: transporte OSM (25%) + 5 vars POI + densidad (10%) + verdes (10%)
  → Comparable con GBA completo

Ciudades configuradas en src/ingesta/config.py:
  rosario, cordoba, mendoza (+ cualquiera que se agregue a CIUDADES)

Uso:
  # Modo parcial (inmediato):
  python src/pipeline/ciudad_interior.py rosario --modo parcial
  python src/pipeline/ciudad_interior.py cordoba --modo parcial
  python src/pipeline/ciudad_interior.py mendoza --modo parcial

  # Modo completo (requiere POIs descargados):
  python src/pipeline/ciudad_interior.py rosario --modo completo
"""
import argparse
import math
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from loguru import logger

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "ingesta"))

from ingesta.config import CIUDADES  # noqa: E402

DATA_RAW       = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
SCORES_OUT     = DATA_PROCESSED / "scores"
PUBLIC_DIR     = ROOT / "apps" / "web" / "public"
RADIOS_GPKG    = DATA_RAW / "indec" / "radios_censales.gpkg"

CRS_METRIC = "EPSG:5347"

# Pesos modo PARCIAL — 3 variables censales (requiere datos de población)
WEIGHTS_PARCIAL = {
    "densidad_pob_norm":   0.50,
    "hogares_tot_norm":    0.30,
    "tasa_ocup_norm":      0.20,
}

# Pesos modo GEOMETRICO — proxy por tamaño de radio (radios pequeños = zonas más densas/urbanas)
# Usado cuando el GPKG nacional no tiene datos censales
WEIGHTS_GEOMETRICO = {
    "area_inv_norm": 1.00,
}

# Pesos modo COMPLETO (con POIs OSM, sin subte — usa nearest transporte POI)
WEIGHTS_COMPLETO = {
    "dist_transporte_score":          0.25,
    "poi_total_density_norm":         0.20,
    "div_entropy_ex_transporte_norm": 0.20,
    "poi_espacios_verdes_norm":       0.10,
    "densidad_pob_norm":              0.10,
    "poi_educacion_norm":             0.08,
    "poi_salud_norm":                 0.07,
}

POI_CATEGORIES = ["comercio", "educacion", "espacios_verdes", "oficinas", "salud", "transporte"]


def _minmax(series: pd.Series) -> pd.Series:
    lo, hi = series.min(), series.max()
    if hi == lo:
        return pd.Series(0.5, index=series.index)
    return (series - lo) / (hi - lo)


def _shannon_h(row: pd.Series, cats: list) -> float:
    counts = [row.get(f"poi_{c}_count", 0) for c in cats if row.get(f"poi_{c}_count", 0) > 0]
    if len(counts) < 2:
        return 0.0
    total = sum(counts)
    probs = [c / total for c in counts]
    h = -sum(p * math.log(p) for p in probs)
    return round(h / math.log(len(counts)), 4)


# ── Extracción de radios ───────────────────────────────────────────────────────

def extract_city_radios(city_id: str, cfg: dict) -> gpd.GeoDataFrame:
    if not RADIOS_GPKG.exists():
        raise FileNotFoundError(f"Radios nacionales no encontrados: {RADIOS_GPKG}")

    logger.info(f"Leyendo radios de {RADIOS_GPKG} ...")
    gdf = gpd.read_file(RADIOS_GPKG)
    prov = cfg["provincia"]
    deptos = _depto_names(city_id)

    if deptos:
        mask = (gdf["provincia"] == prov) & (gdf["departamento"].isin(deptos))
        city_radios = gdf[mask].copy()
    else:
        # Bbox clip (no depto mapping for this city)
        lon_min, lat_min, lon_max, lat_max = cfg["bbox"]
        gdf_wgs = gdf.to_crs("EPSG:4326")
        centroids = gdf_wgs.geometry.centroid
        bbox_mask = (
            (centroids.x >= lon_min) & (centroids.x <= lon_max) &
            (centroids.y >= lat_min) & (centroids.y <= lat_max)
        )
        city_radios = gdf[bbox_mask].copy()

    if city_radios.empty:
        raise ValueError(f"No se encontraron radios para {city_id} ({prov}, deptos={deptos})")

    city_radios = city_radios[city_radios.geometry.is_valid & ~city_radios.geometry.is_empty]
    logger.info(f"  {city_id}: {len(city_radios)} radios censales")
    return city_radios


def _depto_names(city_id: str) -> list[str] | None:
    """Devuelve lista de departamentos para filtrar. None = usar bbox."""
    mapping: dict[str, list[str] | None] = {
        "rosario": ["Rosario"],
        "cordoba": ["Capital"],
        # Gran Mendoza: los 4 deptos del área metropolitana
        "mendoza": ["Capital", "Godoy Cruz", "Guaymallén", "Las Heras"],
    }
    return mapping.get(city_id)


# ── Modo PARCIAL ───────────────────────────────────────────────────────────────

def score_parcial(radios: gpd.GeoDataFrame, city_id: str, cfg: dict) -> gpd.GeoDataFrame:
    """
    Score parcial con datos censales (tot_pob, tot_hog, viv_ocup).
    Si el GPKG no tiene estas columnas, delega a score_geometrico.
    """
    has_census = all(c in radios.columns for c in ["tot_pob", "tot_hog", "viv_ocup"])
    if not has_census:
        logger.warning("GPKG sin datos censales → usando score geométrico (proxy por área de radio)")
        return score_geometrico(radios, city_id, cfg)

    logger.info("Modo PARCIAL — 3 variables censales")
    df = radios.copy()

    df_proj = df.to_crs(CRS_METRIC)
    area_km2 = df_proj.geometry.area / 1e6
    area_safe = area_km2.replace(0, np.nan)

    pob  = pd.to_numeric(df["tot_pob"], errors="coerce").fillna(0)
    hog  = pd.to_numeric(df["tot_hog"], errors="coerce").fillna(0)
    vocc = pd.to_numeric(df["viv_ocup"], errors="coerce").fillna(0)
    vhab = pd.to_numeric(df.get("viv_part_hab", pd.Series(1, index=df.index)), errors="coerce").fillna(1)
    vhab = vhab.replace(0, np.nan)

    df["densidad_pob"] = (pob / area_safe).fillna(0)
    df["hogares_tot"]  = (hog / area_safe).fillna(0)
    df["tasa_ocup"]    = (vocc / vhab).fillna(0).clip(0, 1)

    df["densidad_pob_norm"] = _minmax(df["densidad_pob"])
    df["hogares_tot_norm"]  = _minmax(df["hogares_tot"])
    df["tasa_ocup_norm"]    = _minmax(df["tasa_ocup"])

    raw = sum(df[feat] * w for feat, w in WEIGHTS_PARCIAL.items())
    df["alpha_score"]   = (raw * 100).round(1)
    df["score_version"] = f"parcial_{city_id}"
    df["score_tipo"]    = "parcial"
    df["ciudad"]        = city_id
    df["nombre_ciudad"] = cfg["nombre"]
    df["alpha_quintil"] = _safe_qcut(df["alpha_score"])

    logger.info(
        f"  Score parcial — media: {df['alpha_score'].mean():.1f} | "
        f"mediana: {df['alpha_score'].median():.1f} | "
        f"max: {df['alpha_score'].max():.1f}"
    )
    return df


def score_geometrico(radios: gpd.GeoDataFrame, city_id: str, cfg: dict) -> gpd.GeoDataFrame:
    """
    Score proxy basado en área del radio censal.
    Radios pequeños = zonas más densas/urbanas = score más alto.
    Transparente: score_tipo = 'geometrico' (sin datos censales ni POIs).
    """
    logger.info("Modo GEOMÉTRICO — proxy por área de radio censal")
    df = radios.copy()

    df_proj = df.to_crs(CRS_METRIC)
    area_km2 = df_proj.geometry.area / 1e6
    df["area_km2"] = area_km2.values

    # Score = inverso del área normalizada (área chica → zona más densa → score alto)
    df["area_inv_norm"] = 1.0 - _minmax(df["area_km2"])
    df["alpha_score"]   = (df["area_inv_norm"] * 100).round(1)
    df["score_version"] = f"geometrico_{city_id}"
    df["score_tipo"]    = "geometrico"
    df["ciudad"]        = city_id
    df["nombre_ciudad"] = cfg["nombre"]
    df["densidad_pob"]  = np.nan
    df["tot_pob"]       = np.nan
    df["alpha_quintil"] = _safe_qcut(df["alpha_score"])

    logger.info(
        f"  Score geométrico — media: {df['alpha_score'].mean():.1f} | "
        f"mediana: {df['alpha_score'].median():.1f} | "
        f"max: {df['alpha_score'].max():.1f}"
    )
    return df


def _safe_qcut(scores: pd.Series) -> pd.Series:
    try:
        result = pd.qcut(scores, q=5, labels=[1, 2, 3, 4, 5], duplicates="drop")
        # Add missing categories if drop removed some
        for cat in [1, 2, 3, 4, 5]:
            if cat not in result.cat.categories:
                result = result.cat.add_categories([cat])
        return result.fillna(3).astype(int)
    except Exception:
        # Last resort: rank-based quintiles
        return pd.Series(
            pd.qcut(scores.rank(method="first"), q=5, labels=[1, 2, 3, 4, 5]).astype(int),
            index=scores.index,
        )


# ── Modo COMPLETO ──────────────────────────────────────────────────────────────

def score_completo(radios: gpd.GeoDataFrame, city_id: str, cfg: dict) -> gpd.GeoDataFrame:
    from scoring import load_all_pois, build_radio_features
    logger.info("Modo COMPLETO — con POIs OSM")

    osm_proc = DATA_PROCESSED / "osm"
    prefix = f"{city_id}_"
    pois = load_all_pois(osm_proc, prefix=prefix)

    # Transporte POIs como proxy de accesibilidad (no hay subte)
    if "transporte" in pois:
        stops_gdf = pois["transporte"][["geometry"]].copy()
        stops_gdf["stop_name"] = "transporte"
    else:
        logger.warning("Sin POIs de transporte — usando centroides de radios como fallback")
        proj = radios.to_crs(CRS_METRIC)
        stops_gdf = gpd.GeoDataFrame(
            {"stop_name": ["centroide"] * len(proj)},
            geometry=proj.geometry.centroid,
            crs=CRS_METRIC,
        ).to_crs("EPSG:4326")

    df = build_radio_features(radios, pois, stops_gdf)

    df["dist_transporte_score"] = 1.0 - _minmax(df["dist_subte_m"])
    df["poi_total_density_norm"]         = _minmax(df["poi_total_density"])
    df["div_entropy_ex_transporte_norm"] = _minmax(df["div_entropy_ex_transporte"])
    df["poi_espacios_verdes_norm"]       = _minmax(df["poi_espacios_verdes_density"])
    df["densidad_pob_norm"]              = _minmax(df["densidad_pob"])
    df["poi_educacion_norm"]             = _minmax(df["poi_educacion_density"])
    df["poi_salud_norm"]                 = _minmax(df["poi_salud_density"])

    raw = sum(df[feat] * w for feat, w in WEIGHTS_COMPLETO.items())
    df["alpha_score"]   = (raw * 100).round(1)
    df["score_version"] = f"completo_{city_id}"
    df["score_tipo"]    = "completo"
    df["ciudad"]        = city_id
    df["nombre_ciudad"] = cfg["nombre"]
    df["alpha_quintil"] = _safe_qcut(df["alpha_score"])

    logger.info(
        f"  Score completo — media: {df['alpha_score'].mean():.1f} | "
        f"mediana: {df['alpha_score'].median():.1f}"
    )
    return df


# ── Export ─────────────────────────────────────────────────────────────────────

def export(df: gpd.GeoDataFrame, city_id: str) -> None:
    SCORES_OUT.mkdir(parents=True, exist_ok=True)

    keep_cols = [c for c in [
        "link", "ciudad", "nombre_ciudad", "provincia", "departamento",
        "alpha_score", "alpha_quintil", "score_version", "score_tipo",
        "tot_pob", "densidad_pob",
        "geometry",
    ] if c in df.columns]

    gdf_out = df[keep_cols].to_crs("EPSG:4326")

    gpkg_path = SCORES_OUT / f"{city_id}_radio_scores.gpkg"
    gdf_out.to_file(gpkg_path, driver="GPKG")
    logger.info(f"GeoPackage → {gpkg_path}")

    geojson_path = PUBLIC_DIR / f"{city_id}_alpha_scores.geojson"
    gdf_out.to_file(geojson_path, driver="GeoJSON")
    import os
    size_kb = os.path.getsize(geojson_path) // 1024
    logger.info(f"GeoJSON → {geojson_path}  ({size_kb} KB)")


# ── Main ───────────────────────────────────────────────────────────────────────

def run(city_id: str, modo: str = "parcial") -> gpd.GeoDataFrame:
    if city_id not in CIUDADES:
        raise ValueError(f"Ciudad '{city_id}' no configurada. Opciones: {list(CIUDADES)}")

    cfg = CIUDADES[city_id]
    logger.info(f"=== Alpha Score {cfg['nombre']} ({city_id}) — modo {modo} ===")

    radios = extract_city_radios(city_id, cfg)

    if modo == "parcial":
        df = score_parcial(radios, city_id, cfg)
    elif modo == "completo":
        df = score_completo(radios, city_id, cfg)
    else:
        raise ValueError(f"modo debe ser 'parcial' o 'completo', no '{modo}'")

    export(df, city_id)
    return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("city", choices=list(CIUDADES.keys()), help="ID de ciudad")
    parser.add_argument("--modo", choices=["parcial", "completo"], default="parcial")
    args = parser.parse_args()
    run(args.city, args.modo)
