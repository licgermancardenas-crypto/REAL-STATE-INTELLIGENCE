"""
Alpha Score GBA — scoring de radios censales del Conurbano Bonaerense.

Modo COMPLETO (cuando existen datos POI en data/processed/osm/gba_*_clean/):
  Mismo pipeline que CABA v1 pero reemplaza dist_subte_score por dist_tren_score
  (distancia al ferrocarril/colectivo, desde transporte POIs OSM).

  Pesos v1_gba:
    dist_tren_score            25%  acceso al transporte masivo (tren suburbano)
    poi_total_density_norm     20%  vitalidad urbana
    div_entropy_ex_t_norm      20%  mezcla de usos
    poi_espacios_verdes_norm   10%  calidad de vida
    densidad_pob_norm          10%  barrio consolidado
    poi_educacion_norm          8%  servicios
    poi_salud_norm              7%  servicios

Modo PARCIAL (fallback sin POIs — 3 variables censales):
  densidad_pob_norm   50%
  densidad_hog_norm   30%
  tasa_ocupacion_norm 20%

CRS métrico: EPSG:5347  POSGAR 2007 / Argentina faja 3.

Uso:
  python src/models/scoring_gba.py
"""
import math
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from loguru import logger

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

DATA_PROCESSED = ROOT / "data" / "processed"
SCORES_OUT     = DATA_PROCESSED / "scores"

CRS_METRIC = "EPSG:5347"

# Conurbano Bonaerense bbox
CONURBANO_BBOX = (-59.1, -35.1, -58.2, -34.3)
MIN_RADIOS     = 50

# Fuente: Georef API INDEC (apis.datos.gob.ar/georef) + validación GADM
# Verificado 2026-06-23. Clave = LINK[2:5] (código departamento INDEC PBA).
CODIGO_PARTIDO = {
    "028": "Almirante Brown",
    "035": "Avellaneda",
    "091": "Berazategui",
    "119": "Brandsen",
    "126": "Campana",
    "134": "Cañuelas",
    "252": "Escobar",
    "266": "Exaltación de la Cruz",
    "260": "Esteban Echeverría",
    "270": "Ezeiza",
    "274": "Florencio Varela",
    "329": "General Las Heras",
    "364": "General Rodríguez",
    "371": "General San Martín",
    "408": "Hurlingham",
    "410": "Ituzaingó",
    "412": "José C. Paz",
    "427": "La Matanza",
    "434": "Lanús",
    "441": "La Plata",
    "483": "Lobos",
    "490": "Lomas de Zamora",
    "497": "Luján",
    "515": "Malvinas Argentinas",
    "525": "Marcos Paz",
    "539": "Merlo",
    "560": "Moreno",
    "568": "Morón",
    "638": "Pilar",
    "648": "Presidente Perón",
    "658": "Quilmes",
    "749": "San Fernando",
    "756": "San Isidro",
    "760": "San Miguel",
    "778": "San Vicente",
    "805": "Tigre",
    "840": "Tres de Febrero",
    "861": "Vicente López",
}

WEIGHTS_V1_GBA = {
    "dist_tren_score":                0.25,
    "poi_total_density_norm":         0.20,
    "div_entropy_ex_transporte_norm": 0.20,
    "poi_espacios_verdes_norm":       0.10,
    "densidad_pob_norm":              0.10,
    "poi_educacion_norm":             0.08,
    "poi_salud_norm":                 0.07,
}
assert abs(sum(WEIGHTS_V1_GBA.values()) - 1.0) < 1e-9

WEIGHTS_PARCIAL = {
    "densidad_pob_norm":   0.50,
    "densidad_hog_norm":   0.30,
    "tasa_ocupacion_norm": 0.20,
}

POI_CATEGORIES = [
    "comercio", "educacion", "espacios_verdes",
    "oficinas", "salud", "transporte",
]


def _minmax(s: pd.Series) -> pd.Series:
    lo, hi = s.min(), s.max()
    return pd.Series(0.5, index=s.index) if hi == lo else (s - lo) / (hi - lo)


def _shannon_h(row: pd.Series, cats: list) -> float:
    counts = [row[f"poi_{c}_count"] for c in cats if row[f"poi_{c}_count"] > 0]
    if len(counts) < 2:
        return 0.0
    total = sum(counts)
    probs = [c / total for c in counts]
    h = -sum(p * math.log(p) for p in probs)
    return round(h / math.log(len(counts)), 4)


def _get_conurbano_radios() -> gpd.GeoDataFrame:
    gdf = gpd.read_file(DATA_PROCESSED / "census" / "pba_radios.gpkg").to_crs("EPSG:4326")
    lon_min, lat_min, lon_max, lat_max = CONURBANO_BBOX
    cx = gdf.geometry.centroid.x
    cy = gdf.geometry.centroid.y
    mask = (cx >= lon_min) & (cx <= lon_max) & (cy >= lat_min) & (cy <= lat_max)
    gdf = gdf[mask & gdf.geometry.is_valid & ~gdf.geometry.is_empty].copy()
    logger.info(f"Conurbano radios: {len(gdf)}")
    return gdf


def _has_poi_data() -> bool:
    """Verifica si hay datos POI procesados para GBA."""
    osm_dir = DATA_PROCESSED / "osm"
    gba_dirs = [d for d in osm_dir.iterdir() if d.is_dir() and d.name.startswith("gba_") and d.name.endswith("_clean")]
    if len(gba_dirs) < 5:
        return False
    # Verificar que al menos la mitad tenga datos de POIs
    has_data = sum(
        1 for d in gba_dirs
        if any((d / f"{cat}.gpkg").exists() for cat in ["comercio", "transporte"])
    )
    return has_data >= len(gba_dirs) // 2


def load_gba_pois() -> dict:
    """Lee todos los GPKG en data/processed/osm/gba_*_clean/."""
    osm_dir = DATA_PROCESSED / "osm"
    pois: dict = {cat: [] for cat in POI_CATEGORIES}

    clean_dirs = sorted([
        d for d in osm_dir.iterdir()
        if d.is_dir() and d.name.startswith("gba_") and d.name.endswith("_clean")
    ])
    logger.info(f"Cargando POIs de {len(clean_dirs)} partidos ...")

    for d in clean_dirs:
        for cat in POI_CATEGORIES:
            gpkg = d / f"{cat}.gpkg"
            if gpkg.exists():
                pois[cat].append(gpd.read_file(gpkg))

    result = {}
    for cat, frames in pois.items():
        if not frames:
            logger.warning(f"  Sin POIs para {cat}")
            continue
        combined = pd.concat(frames, ignore_index=True)
        combined["_wkt"] = combined.geometry.to_wkt(rounding_precision=6)
        combined = combined.drop_duplicates("_wkt").drop(columns="_wkt")
        result[cat] = gpd.GeoDataFrame(combined, crs="EPSG:4326")
        logger.info(f"  {cat}: {len(result[cat]):>7} POIs únicos")

    return result


def extract_rail_stations(pois: dict) -> gpd.GeoDataFrame:
    """
    Extrae estaciones de tren/metro de los POIs de transporte.
    Filtra por railway=station o railway=halt como proxy de transporte masivo.
    """
    if "transporte" not in pois or pois["transporte"].empty:
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")

    t = pois["transporte"]
    station_mask = pd.Series(False, index=t.index)
    if "tag_railway" in t.columns:
        station_mask |= t["tag_railway"].isin(["station", "halt"])
    if "tag_public_transport" in t.columns:
        station_mask |= t["tag_public_transport"] == "station"

    stations = t[station_mask].copy()
    if len(stations) == 0:
        logger.warning("  No se encontraron estaciones de tren en los POIs de transporte")
        logger.warning("  Usando todos los stops de transporte como proxy")
        stations = t.copy()

    logger.info(f"  Estaciones tren/transit: {len(stations)}")
    return stations.reset_index(drop=True)


def build_gba_features(
    radios: gpd.GeoDataFrame,
    pois: dict,
    stations: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """Calcula features por radio (idéntico a CABA pero con dist_tren)."""
    logger.info(f"Features para {len(radios)} radios GBA ...")

    radios_proj = radios.to_crs(CRS_METRIC).copy()
    radios_proj["area_m2"]  = radios_proj.geometry.area
    radios_proj["area_km2"] = radios_proj["area_m2"] / 1e6
    radios_proj = radios_proj.reset_index(drop=True)
    radios_proj["_rid"] = radios_proj.index
    radios_right = radios_proj[["_rid", "geometry"]].copy()

    # POI counts per category
    for cat, gdf_poi in pois.items():
        gdf_proj = gdf_poi.to_crs(CRS_METRIC)[["geometry"]].copy()
        joined = gpd.sjoin(gdf_proj, radios_right, how="left", predicate="within")
        counts = joined.groupby("_rid").size()
        radios_proj[f"poi_{cat}_count"] = (
            counts.reindex(radios_proj["_rid"]).fillna(0).astype(int).values
        )

    for cat in POI_CATEGORIES:
        if f"poi_{cat}_count" not in radios_proj.columns:
            radios_proj[f"poi_{cat}_count"] = 0

    total_pois = sum(radios_proj[f"poi_{cat}_count"].sum() for cat in POI_CATEGORIES)
    logger.info(f"  Total POIs asignados: {int(total_pois):,}")

    # Densidades
    area_safe = radios_proj["area_km2"].replace(0, np.nan)
    for cat in POI_CATEGORIES:
        radios_proj[f"poi_{cat}_density"] = (
            radios_proj[f"poi_{cat}_count"] / area_safe
        ).fillna(0).round(4)

    radios_proj["poi_total_count"] = sum(
        radios_proj[f"poi_{cat}_count"] for cat in POI_CATEGORIES
    )
    radios_proj["poi_total_density"] = (
        radios_proj["poi_total_count"] / area_safe
    ).fillna(0).round(4)

    # Shannon entropy (ex transporte)
    cats_ex_t = [c for c in POI_CATEGORIES if c != "transporte"]
    radios_proj["div_entropy_ex_transporte"] = radios_proj.apply(
        lambda r: _shannon_h(r, cats_ex_t), axis=1
    )

    # Densidad poblacional
    if "tot_pob" in radios_proj.columns:
        radios_proj["densidad_pob"] = (
            radios_proj["tot_pob"].fillna(0) / area_safe
        ).fillna(0).round(1)
    else:
        radios_proj["densidad_pob"] = 0.0

    # Distancia al tren/transit
    logger.info("  Distancias al tren ...")
    stations_proj = stations.to_crs(CRS_METRIC) if len(stations) > 0 else None
    centroids_gdf = gpd.GeoDataFrame(
        {"idx_radio": radios_proj.index},
        geometry=radios_proj.geometry.centroid,
        crs=CRS_METRIC,
    )

    if stations_proj is not None and len(stations_proj) > 0:
        nearest = gpd.sjoin_nearest(
            centroids_gdf,
            stations_proj[["geometry"]].reset_index(drop=True),
            how="left",
            distance_col="dist_tren_m",
        )
        nearest = nearest[~nearest.index.duplicated(keep="first")]
        nearest = nearest.reindex(centroids_gdf.index)
        radios_proj["dist_tren_m"] = nearest["dist_tren_m"].values
    else:
        # Sin datos de estaciones: penalidad máxima proporcional al área
        logger.warning("  Sin estaciones — usando dist_tren_m = 5000 m (fallback)")
        radios_proj["dist_tren_m"] = 5000.0

    radios_proj["dist_tren_m"] = radios_proj["dist_tren_m"].fillna(radios_proj["dist_tren_m"].max())
    logger.info(f"  dist_tren mediana: {radios_proj['dist_tren_m'].median():.0f} m")

    return radios_proj


def compute_gba_score(df: gpd.GeoDataFrame, full_mode: bool) -> gpd.GeoDataFrame:
    if full_mode:
        logger.info("Calculando Alpha Score GBA (modo completo, 7 features) ...")
        df["poi_total_density_norm"]         = _minmax(df["poi_total_density"])
        df["div_entropy_ex_transporte_norm"] = _minmax(df["div_entropy_ex_transporte"])
        df["poi_espacios_verdes_norm"]       = _minmax(df["poi_espacios_verdes_density"])
        df["densidad_pob_norm"]              = _minmax(df["densidad_pob"])
        df["poi_educacion_norm"]             = _minmax(df["poi_educacion_density"])
        df["poi_salud_norm"]                 = _minmax(df["poi_salud_density"])
        df["dist_tren_score"]                = 1.0 - _minmax(df["dist_tren_m"])
        raw = sum(df[feat] * w for feat, w in WEIGHTS_V1_GBA.items())
        df["score_tipo"] = "completo"
    else:
        logger.info("Calculando Alpha Score GBA (modo parcial, 3 features censales) ...")
        area_safe = df["area_km2"].replace(0, np.nan)
        df["densidad_pob_norm"]   = _minmax(df["tot_pob"].fillna(0) / area_safe.fillna(1))
        df["densidad_hog_norm"]   = _minmax(df["hogares"].fillna(0) / area_safe.fillna(1))
        df["viv_part"]  = df["viv_part"].fillna(0).clip(lower=1)
        df["tasa_ocupacion_norm"] = _minmax(
            (df["viv_part_h"].fillna(0) / df["viv_part"]).clip(0, 1)
        )
        raw = sum(df[feat] * w for feat, w in WEIGHTS_PARCIAL.items())
        df["score_tipo"] = "parcial"

    df["alpha_score"]   = (raw * 100).round(1)
    df["alpha_quintil"] = pd.qcut(
        df["alpha_score"], q=5, labels=[1, 2, 3, 4, 5]
    ).astype(int)

    logger.info(
        f"  Score — media: {df['alpha_score'].mean():.1f} | "
        f"mediana: {df['alpha_score'].median():.1f} | "
        f"max: {df['alpha_score'].max():.1f}"
    )
    return df


def run_gba() -> gpd.GeoDataFrame:
    logger.info("=== Alpha Score GBA ===")

    radios = _get_conurbano_radios()
    full_mode = _has_poi_data()
    logger.info(f"Modo: {'COMPLETO (7 features)' if full_mode else 'PARCIAL (3 features censales)'}")

    if full_mode:
        pois     = load_gba_pois()
        stations = extract_rail_stations(pois)
        scored   = build_gba_features(radios, pois, stations)
    else:
        scored = radios.copy()
        scored_proj = scored.to_crs(CRS_METRIC)
        scored["area_m2"]  = scored_proj.geometry.area
        scored["area_km2"] = scored["area_m2"] / 1e6

    scored = compute_gba_score(scored, full_mode=full_mode)

    # Agregar nombre del partido
    scored["depto_code"]     = scored["link"].str[2:5]
    scored["nombre_partido"] = scored["depto_code"].map(CODIGO_PARTIDO).fillna("Desconocido")

    # Simplificar geometría
    scored.geometry = scored.geometry.simplify(0.0001, preserve_topology=True)

    SCORES_OUT.mkdir(parents=True, exist_ok=True)

    base_cols = ["link", "depto_code", "nombre_partido",
                 "alpha_score", "alpha_quintil", "score_tipo",
                 "tot_pob", "densidad_pob", "area_km2", "geometry"]
    poi_cols  = ["poi_total_count", "poi_total_density",
                 "div_entropy_ex_transporte", "dist_tren_m"] if full_mode else []

    out_cols  = [c for c in base_cols + poi_cols if c in scored.columns]

    out_gpkg = SCORES_OUT / "gba_radio_scores.gpkg"
    scored[out_cols].to_crs("EPSG:4326").to_file(out_gpkg, driver="GPKG")
    logger.info(f"GeoPackage → {out_gpkg}")

    out_geojson = ROOT / "apps" / "web" / "public" / "gba_alpha_scores.geojson"
    scored[out_cols].to_crs("EPSG:4326").to_file(out_geojson, driver="GeoJSON")
    import os
    size_kb = os.path.getsize(out_geojson) // 1024
    logger.info(f"GeoJSON → {out_geojson}  ({size_kb} KB, {len(scored)} radios)")

    return scored


if __name__ == "__main__":
    df = run_gba()
    print(f"\nGBA score: {len(df)} radios | modo: {df['score_tipo'].iloc[0]}")
    print(f"Score mediana: {df['alpha_score'].median():.1f}")
    for q in [5, 4, 3, 2, 1]:
        n = int((df["alpha_quintil"] == q).sum())
        print(f"  Q{q}: {n} radios")
