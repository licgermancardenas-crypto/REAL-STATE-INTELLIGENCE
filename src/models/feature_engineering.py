"""
Feature engineering espacial — dos niveles de granularidad.

NIVEL BARRIO (este módulo como script)
  Calcula features de localizacion agregadas para un barrio completo.
  Input:  POIs limpios (data/processed/osm/<ciudad_barrio>_clean/)
          Poligono real GCBA (data/raw/gcba/barrios_caba.geojson)
          Paradas subte  (data/processed/transport/subte_stops.gpkg)
  Output: data/processed/features/<slug>_features.csv

NIVEL RADIO CENSAL (funciones para el modelo de scoring Fase 3)
  poi_density(), street_connectivity(), avg_price_m2(),
  normalize_features(), build_feature_matrix()
  Estas funciones operan sobre GeoDataFrames de radios INDEC.

Features de barrio generadas
  poi_{cat}_count / _density   cantidad y POIs/km2 por categoria
  poi_total_count / _density   suma todas las categorias
  dist_subte_m                 metros al stop de subte mas cercano
  div_n_cats                   categorias con >= MIN_POIS_SIGNIFICANT POIs
  div_entropy                  Shannon H (0=una cat domina; ln(6)=igual)
  div_entropy_norm             H / ln(n_cats) en [0, 1]

CRS metrico: EPSG:5347  POSGAR 2007 / Argentina faja 3.

Uso:
  python src/models/feature_engineering.py              # Palermo
  python src/models/feature_engineering.py Belgrano     # otro barrio
"""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import geopandas as gpd
from loguru import logger

ROOT           = Path(__file__).parent.parent.parent
DATA_RAW       = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"

BARRIOS_GEOJSON = DATA_RAW  / "gcba" / "barrios_caba.geojson"
SUBTE_STOPS     = DATA_PROCESSED / "transport" / "subte_stops.gpkg"
FEATURES_OUT    = DATA_PROCESSED / "features"

CRS_METRIC           = "EPSG:5347"  # POSGAR 2007 / Argentina faja 3
MIN_POIS_SIGNIFICANT = 10

POI_CATEGORIES = [
    "comercio",
    "educacion",
    "espacios_verdes",
    "oficinas",
    "salud",
    "transporte",
]


# ═══════════════════════════════════════════════════════════════════════════════
# NIVEL BARRIO
# ═══════════════════════════════════════════════════════════════════════════════

def _load_barrio(nombre: str) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(BARRIOS_GEOJSON)
    match = gdf[gdf["nombre"].str.lower() == nombre.lower()]
    if match.empty:
        avail = sorted(gdf["nombre"].tolist())
        raise ValueError(f"Barrio '{nombre}' no encontrado. Disponibles: {avail}")
    return match.to_crs("EPSG:4326")


def _area_km2_from_row(row) -> float:
    # area_metro del GeoJSON GCBA en m2, calculado en POSGAR/Gauss-Krüger
    # mas preciso que re-proyectar la geometria WGS84
    return float(row["area_metro"]) / 1_000_000


def _shannon_entropy(counts: list) -> tuple:
    """H y H_norm en [0,1]. Excluye categorias con 0 POIs."""
    counts = [c for c in counts if c > 0]
    if not counts:
        return 0.0, 0.0
    total = sum(counts)
    probs = [c / total for c in counts]
    h = -sum(p * math.log(p) for p in probs)
    h_norm = h / math.log(len(counts)) if len(counts) > 1 else 1.0
    return round(h, 4), round(h_norm, 4)


def _compute_poi_densities(area_km2: float, clean_dir: Path) -> tuple:
    feats: dict = {}
    counts: list = []
    for cat in POI_CATEGORIES:
        path = clean_dir / f"{cat}.gpkg"
        n = len(gpd.read_file(path)) if path.exists() else 0
        if not path.exists():
            logger.warning(f"  No encontrado: {path.name} — asumiendo 0")
        feats[f"poi_{cat}_count"]   = n
        feats[f"poi_{cat}_density"] = round(n / area_km2, 4) if area_km2 else 0.0
        counts.append(n)
    total = sum(counts)
    feats["poi_total_count"]   = total
    feats["poi_total_density"] = round(total / area_km2, 4) if area_km2 else 0.0
    logger.info(f"  Densidades OK — {total} POIs en {area_km2:.3f} km2")
    return feats, counts


def _compute_subte_distance(centroid_geom) -> tuple:
    """Distancia metrica al stop de subte mas cercano. Devuelve (metros, nombre)."""
    stops_raw = gpd.read_file(SUBTE_STOPS)
    stops_raw["stop_lat"] = pd.to_numeric(stops_raw["stop_lat"], errors="coerce")
    stops_raw["stop_lon"] = pd.to_numeric(stops_raw["stop_lon"], errors="coerce")
    stops_raw = stops_raw.dropna(subset=["stop_lat", "stop_lon"])

    stops_gdf = gpd.GeoDataFrame(
        stops_raw,
        geometry=gpd.points_from_xy(stops_raw["stop_lon"], stops_raw["stop_lat"]),
        crs="EPSG:4326",
    ).to_crs(CRS_METRIC)

    centroid_proj = (
        gpd.GeoDataFrame(geometry=[centroid_geom], crs="EPSG:4326")
        .to_crs(CRS_METRIC)
        .geometry.iloc[0]
    )

    distances   = stops_gdf.geometry.distance(centroid_proj)
    nearest_idx = distances.idxmin()
    min_dist    = distances.loc[nearest_idx]
    stop_name   = (
        stops_raw.loc[nearest_idx, "stop_name"]
        if "stop_name" in stops_raw.columns else "N/A"
    )
    logger.info(f"  Subte mas cercano: '{stop_name}' — {min_dist:.0f} m")
    return round(float(min_dist), 1), str(stop_name)


def build_barrio_features(barrio: str = "Palermo", ciudad_id: str = "caba") -> pd.DataFrame:
    """
    Calcula el vector de features para un barrio completo y lo guarda como CSV.
    """
    logger.info(f"Feature engineering barrio: {barrio} ({ciudad_id})")

    barrio_gdf = _load_barrio(barrio)
    row        = barrio_gdf.iloc[0]
    area_km2   = _area_km2_from_row(row)
    centroid   = row.geometry.centroid

    logger.info(f"  Area: {area_km2:.3f} km2 | Centroide: ({centroid.y:.4f}, {centroid.x:.4f})")

    slug      = f"{ciudad_id}_{barrio.lower().replace(' ', '_')}"
    clean_dir = DATA_PROCESSED / "osm" / f"{slug}_clean"
    if not clean_dir.exists():
        raise FileNotFoundError(
            f"POIs limpios no encontrados: {clean_dir}\n"
            "Corre primero: python src/utils/clip_pois.py"
        )

    density_feats, counts = _compute_poi_densities(area_km2, clean_dir)
    dist_subte, stop_name = _compute_subte_distance(centroid)
    n_sig                 = sum(1 for c in counts if c >= MIN_POIS_SIGNIFICANT)
    h, h_norm             = _shannon_entropy(counts)

    record = {
        "barrio":             barrio,
        "ciudad":             ciudad_id,
        "area_km2":           round(area_km2, 4),
        "centroid_lat":       round(centroid.y, 6),
        "centroid_lon":       round(centroid.x, 6),
        "dist_subte_m":       dist_subte,
        "nearest_subte_stop": stop_name,
        **density_feats,
        "div_n_cats":         n_sig,
        "div_entropy":        h,
        "div_entropy_norm":   h_norm,
    }

    df = pd.DataFrame([record])
    FEATURES_OUT.mkdir(parents=True, exist_ok=True)
    out_path = FEATURES_OUT / f"{slug}_features.csv"
    df.to_csv(out_path, index=False)
    logger.info(f"Features guardadas -> {out_path}")
    return df


# ═══════════════════════════════════════════════════════════════════════════════
# NIVEL RADIO CENSAL — para el modelo de scoring Fase 3
# ═══════════════════════════════════════════════════════════════════════════════

def poi_density(radios: gpd.GeoDataFrame, pois: gpd.GeoDataFrame, radius_m: int = 500) -> pd.Series:
    """POIs dentro de radius_m metros del centroide de cada radio."""
    radios_p = radios.to_crs(epsg=22185)
    pois_p   = pois.to_crs(epsg=22185)
    counts = [
        len(pois_p[pois_p.geometry.within(c.buffer(radius_m))])
        for c in radios_p.geometry.centroid
    ]
    return pd.Series(counts, index=radios.index, name="poi_density_500m")


def street_connectivity(streets: gpd.GeoDataFrame, radios: gpd.GeoDataFrame) -> pd.Series:
    """Metros de calle por km² (proxy de conectividad urbana)."""
    radios_p  = radios.to_crs(epsg=22185)
    streets_p = streets.to_crs(epsg=22185)
    joined    = gpd.sjoin(streets_p, radios_p[["geometry"]], how="left", predicate="intersects")
    street_len = joined.groupby("index_right").apply(lambda g: g.geometry.length.sum())
    area_km2   = radios_p.geometry.area / 1e6
    density    = (street_len / area_km2).reindex(radios.index).fillna(0)
    return density.rename("street_connectivity")


def avg_price_m2(listings: pd.DataFrame, radios: gpd.GeoDataFrame) -> pd.Series:
    """Precio promedio USD/m² por radio censal."""
    gdf = gpd.GeoDataFrame(
        listings,
        geometry=gpd.points_from_xy(listings["lon"], listings["lat"]),
        crs="EPSG:4326",
    )
    joined = gpd.sjoin(gdf, radios[["geometry"]], how="left", predicate="within")
    return (
        joined.groupby("index_right")["price_usd_m2"]
        .mean()
        .reindex(radios.index)
        .rename("avg_price_usd_m2")
    )


def normalize_features(df: pd.DataFrame) -> pd.DataFrame:
    """Min-max normalizacion por columna."""
    result = df.copy()
    for col in df.select_dtypes(include=[np.number]).columns:
        col_min, col_max = df[col].min(), df[col].max()
        if col_max > col_min:
            result[col] = (df[col] - col_min) / (col_max - col_min)
        else:
            result[col] = 0.0
    return result


def build_feature_matrix(
    radios: gpd.GeoDataFrame,
    pois: gpd.GeoDataFrame | None = None,
    streets: gpd.GeoDataFrame | None = None,
    listings: pd.DataFrame | None = None,
    transit_coverage: pd.Series | None = None,
) -> pd.DataFrame:
    """Construye la matriz de features por radio censal para el modelo de scoring."""
    features = pd.DataFrame(index=radios.index)

    if pois is not None:
        features["poi_density_500m"] = poi_density(radios, pois)
    if streets is not None:
        features["street_connectivity"] = street_connectivity(streets, radios)
    if listings is not None:
        features["avg_price_usd_m2"] = avg_price_m2(listings, radios)
    if transit_coverage is not None:
        features["transit_stops_500m"] = transit_coverage.reindex(radios.index).fillna(0)
    if "TOTAL_POB" in radios.columns:
        area_km2 = radios.to_crs(epsg=22185).geometry.area / 1e6
        features["densidad_pob"] = (
            pd.to_numeric(radios["TOTAL_POB"], errors="coerce") / area_km2
        ).fillna(0)

    features = features.fillna(features.median(numeric_only=True))
    logger.info(f"Feature matrix: {features.shape[0]} radios x {features.shape[1]} features")
    return features


# ═══════════════════════════════════════════════════════════════════════════════
# Report
# ═══════════════════════════════════════════════════════════════════════════════

def print_barrio_features(df: pd.DataFrame) -> None:
    row  = df.iloc[0]
    area = row["area_km2"]
    sep  = "-" * 56

    print(f"\n=== {row['barrio'].upper()} ({row['ciudad'].upper()}) ===")
    print(f"  Area real:  {area:.3f} km2")
    print(f"  Centroide:  lat={row['centroid_lat']}, lon={row['centroid_lon']}")
    print(f"  Subte mas cercano: {row['nearest_subte_stop']}  ({row['dist_subte_m']:.0f} m)")

    print(f"\n  -- Densidades POI --")
    print(f"  {'Categoria':<20} {'Count':>6}   {'Density/km2':>11}   {'% total':>7}")
    print("  " + sep)
    total_count = int(row["poi_total_count"])
    for cat in POI_CATEGORIES:
        n   = int(row[f"poi_{cat}_count"])
        d   = row[f"poi_{cat}_density"]
        pct = n / total_count * 100 if total_count else 0
        print(f"  {cat:<20} {n:>6}   {d:>11.2f}   {pct:>6.1f}%")
    print("  " + sep)
    print(f"  {'TOTAL':<20} {total_count:>6}   {row['poi_total_density']:>11.2f}")

    print(f"\n  -- Diversidad de POIs --")
    print(f"  Categorias >= {MIN_POIS_SIGNIFICANT} POIs:  {int(row['div_n_cats'])}/6")
    print(f"  Shannon H:               {row['div_entropy']:.4f}  (max ln(6)={math.log(6):.4f})")
    print(f"  H normalizada (0-1):     {row['div_entropy_norm']:.4f}")
    quality = (
        "Alta diversidad"
        if row["div_entropy_norm"] > 0.8
        else "Diversidad media (transporte domina parcialmente)"
        if row["div_entropy_norm"] > 0.6
        else "Baja diversidad (una cat domina)"
    )
    print(f"  Lectura:                 {quality}")
    print()


if __name__ == "__main__":
    barrio = sys.argv[1] if len(sys.argv) > 1 else "Palermo"
    ciudad = sys.argv[2] if len(sys.argv) > 2 else "caba"
    df = build_barrio_features(barrio, ciudad)
    print_barrio_features(df)
