"""
SimpleMaps ARG — base de localidades con coordenadas.
URL: https://simplemaps.com/country/ar/

Free tier: ~47.000 localidades con lat, lng, city, admin_name, population.
Descarga manual del CSV desde el sitio → guardar en data/raw/simplemaps/ar.csv

Columnas del CSV:
  city, city_ascii, lat, lng, country, iso2, iso3,
  admin_name, admin1, capital, population, id
"""
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from loguru import logger
from config import SIMPLEMAPS_CSV, DATA_PROCESSED


DOWNLOAD_URL = "https://simplemaps.com/country/ar/"


def load_localidades(min_population: int = 0) -> gpd.GeoDataFrame:
    """
    Carga el CSV de SimpleMaps y devuelve un GeoDataFrame de puntos.
    min_population: filtrar por población mínima (0 = todo).
    """
    if not SIMPLEMAPS_CSV.exists():
        logger.warning(
            f"CSV SimpleMaps no encontrado en {SIMPLEMAPS_CSV}\n"
            f"Descargar desde: {DOWNLOAD_URL}\n"
            f"Guardar como: {SIMPLEMAPS_CSV}"
        )
        return gpd.GeoDataFrame()

    df = pd.read_csv(SIMPLEMAPS_CSV, dtype={"population": str})
    df["population"] = pd.to_numeric(df["population"].str.replace(",", ""), errors="coerce").fillna(0)
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lng"] = pd.to_numeric(df["lng"], errors="coerce")
    df = df.dropna(subset=["lat", "lng"])

    if min_population > 0:
        df = df[df["population"] >= min_population]

    gdf = gpd.GeoDataFrame(
        df,
        geometry=[Point(row.lng, row.lat) for _, row in df.iterrows()],
        crs="EPSG:4326",
    )
    logger.info(f"SimpleMaps: {len(gdf)} localidades cargadas (pop >= {min_population})")
    return gdf


def get_localidades_provincia(provincia: str, min_population: int = 0) -> gpd.GeoDataFrame:
    """Filtra por provincia (columna admin_name)."""
    gdf = load_localidades(min_population)
    if gdf.empty:
        return gdf
    return gdf[gdf["admin_name"].str.contains(provincia, case=False, na=False)]


def save_localidades_procesadas(min_population: int = 1000) -> None:
    """Guarda localidades con población >= min_population como GPKG."""
    gdf = load_localidades(min_population)
    if gdf.empty:
        return
    out = DATA_PROCESSED / "simplemaps"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"localidades_pop{min_population}.gpkg"
    gdf.to_file(path, driver="GPKG")
    logger.info(f"Guardado → {path}")


def get_city_coords(city_name: str) -> tuple[float, float] | None:
    """
    Devuelve (lat, lon) de una localidad por nombre.
    Útil para centrar mapas sin geocoding externo.
    """
    gdf = load_localidades()
    if gdf.empty:
        return None
    match = gdf[gdf["city_ascii"].str.lower() == city_name.lower()]
    if match.empty:
        match = gdf[gdf["city"].str.lower() == city_name.lower()]
    if match.empty:
        return None
    row = match.iloc[0]
    return (row["lat"], row["lng"])


if __name__ == "__main__":
    # Estadísticas del dataset
    gdf = load_localidades()
    if not gdf.empty:
        print(f"Total localidades: {len(gdf)}")
        print(f"Provincias: {gdf['admin_name'].nunique()}")
        print(f"Con población > 10k: {len(gdf[gdf['population'] > 10000])}")
        print(gdf[gdf["population"] > 100000][["city", "admin_name", "population"]].to_string())
