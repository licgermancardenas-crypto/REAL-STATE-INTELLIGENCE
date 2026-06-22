"""
Feature engineering espacial para el modelo Alpha Score.
Input: GeoDataFrame de radios censales + POIs OSM + listings
Output: DataFrame con features por radio censal
"""
import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import Point


def compute_poi_density(radios: gpd.GeoDataFrame, pois: gpd.GeoDataFrame, radius_m: int = 500) -> pd.Series:
    """POIs dentro de radio_m metros del centroide de cada radio censal."""
    radios_proj = radios.to_crs(epsg=22185)  # POSGAR 2007 / Argentina 5 — metros
    pois_proj = pois.to_crs(epsg=22185)
    centroids = radios_proj.geometry.centroid
    counts = []
    for c in centroids:
        buf = c.buffer(radius_m)
        counts.append(len(pois_proj[pois_proj.geometry.within(buf)]))
    return pd.Series(counts, index=radios.index, name="poi_density_500m")


def compute_street_connectivity(streets: gpd.GeoDataFrame, radios: gpd.GeoDataFrame) -> pd.Series:
    """Metros de calle por km² como proxy de conectividad."""
    radios_proj = radios.to_crs(epsg=22185)
    streets_proj = streets.to_crs(epsg=22185)
    joined = gpd.sjoin(streets_proj, radios_proj[["geometry"]], how="left", predicate="intersects")
    street_len = joined.groupby("index_right").apply(lambda g: g.geometry.length.sum())
    area_km2 = radios_proj.geometry.area / 1e6
    density = street_len.divide(area_km2).fillna(0)
    return density.rename("street_connectivity")


def compute_price_features(listings: pd.DataFrame, radios: gpd.GeoDataFrame) -> pd.DataFrame:
    """Precio promedio USD/m² y delta interanual por radio."""
    gdf_listings = gpd.GeoDataFrame(
        listings,
        geometry=gpd.points_from_xy(listings.lon, listings.lat),
        crs="EPSG:4326",
    )
    joined = gpd.sjoin(gdf_listings, radios[["geometry"]], how="left", predicate="within")
    stats = joined.groupby("index_right")["price_usd_m2"].agg(["mean", "std"]).rename(
        columns={"mean": "avg_price_usd_m2", "std": "price_volatility"}
    )
    return stats


def build_feature_matrix(
    radios: gpd.GeoDataFrame,
    pois: gpd.GeoDataFrame,
    streets: gpd.GeoDataFrame,
    listings: pd.DataFrame,
) -> pd.DataFrame:
    features = radios[["geometry"]].copy()
    features["poi_density_500m"] = compute_poi_density(radios, pois)
    features["street_connectivity"] = compute_street_connectivity(streets, radios)
    price_feats = compute_price_features(listings, radios)
    features = features.join(price_feats, how="left")
    features = features.fillna(features.median(numeric_only=True))
    return features.drop(columns=["geometry"])
