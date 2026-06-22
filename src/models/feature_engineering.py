"""
Feature engineering espacial para el modelo de scoring.
Input: radios censales (GeoDataFrame) + POIs + paradas GTFS + isócronas ORS
Output: DataFrame con features normalizadas por radio censal
"""
import numpy as np
import pandas as pd
import geopandas as gpd
from loguru import logger


def poi_density(radios: gpd.GeoDataFrame, pois: gpd.GeoDataFrame, radius_m: int = 500) -> pd.Series:
    radios_p = radios.to_crs(epsg=22185)
    pois_p = pois.to_crs(epsg=22185)
    counts = [
        len(pois_p[pois_p.geometry.within(c.buffer(radius_m))])
        for c in radios_p.geometry.centroid
    ]
    return pd.Series(counts, index=radios.index, name="poi_density_500m")


def street_connectivity(streets: gpd.GeoDataFrame, radios: gpd.GeoDataFrame) -> pd.Series:
    """Metros de calle por km² (proxy de conectividad urbana)."""
    radios_p = radios.to_crs(epsg=22185)
    streets_p = streets.to_crs(epsg=22185)
    joined = gpd.sjoin(streets_p, radios_p[["geometry"]], how="left", predicate="intersects")
    street_len = joined.groupby("index_right").apply(lambda g: g.geometry.length.sum())
    area_km2 = radios_p.geometry.area / 1e6
    density = (street_len / area_km2).reindex(radios.index).fillna(0)
    return density.rename("street_connectivity")


def avg_price_m2(listings: pd.DataFrame, radios: gpd.GeoDataFrame) -> pd.Series:
    """Precio promedio USD/m² por radio censal."""
    gdf = gpd.GeoDataFrame(
        listings,
        geometry=gpd.points_from_xy(listings["lon"], listings["lat"]),
        crs="EPSG:4326",
    )
    joined = gpd.sjoin(gdf, radios[["geometry"]], how="left", predicate="within")
    return joined.groupby("index_right")["price_usd_m2"].mean().reindex(radios.index).rename("avg_price_usd_m2")


def normalize_features(df: pd.DataFrame) -> pd.DataFrame:
    """Min-max normalización por columna."""
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
    logger.info(f"Feature matrix: {features.shape[0]} radios × {features.shape[1]} features")
    return features
