"""
GTFS Subte y Trenes metropolitanos — red de transporte público CABA/AMBA.
Fuentes:
  - Subte (Metrovias): https://www.metrovias.com.ar/gtfs/metrovias_gtfs.zip
  - Trenes (Ministerio de Transporte): https://datos.transporte.gob.ar
"""
import io
import zipfile
import httpx
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from loguru import logger
from config import GTFS_SUBTE_URL, DATA_RAW, DATA_PROCESSED


def download_gtfs(url: str, nombre: str) -> dict[str, pd.DataFrame]:
    """Descarga y parsea un feed GTFS. Devuelve dict de DataFrames por archivo."""
    logger.info(f"Descargando GTFS {nombre}: {url}")
    resp = httpx.get(url, timeout=120, follow_redirects=True)
    resp.raise_for_status()

    out_dir = DATA_RAW / "gtfs" / nombre
    out_dir.mkdir(parents=True, exist_ok=True)

    tables: dict[str, pd.DataFrame] = {}
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        for name in zf.namelist():
            if name.endswith(".txt"):
                key = name.replace(".txt", "")
                tables[key] = pd.read_csv(zf.open(name), dtype=str)
                logger.info(f"  {name}: {len(tables[key])} filas")

    return tables


def get_stops_geodataframe(gtfs: dict[str, pd.DataFrame]) -> gpd.GeoDataFrame:
    """Convierte stops.txt a GeoDataFrame de puntos."""
    stops = gtfs.get("stops", pd.DataFrame())
    if stops.empty:
        return gpd.GeoDataFrame()
    stops["lat"] = pd.to_numeric(stops["stop_lat"], errors="coerce")
    stops["lon"] = pd.to_numeric(stops["stop_lon"], errors="coerce")
    stops = stops.dropna(subset=["lat", "lon"])
    geometry = [Point(row.lon, row.lat) for _, row in stops.iterrows()]
    return gpd.GeoDataFrame(stops, geometry=geometry, crs="EPSG:4326")


def compute_transit_coverage(
    radios: gpd.GeoDataFrame,
    stops: gpd.GeoDataFrame,
    radius_m: int = 500,
) -> pd.Series:
    """
    Por radio censal: cantidad de paradas de transporte dentro de radius_m metros.
    Proxy de cobertura de transporte público.
    """
    radios_proj = radios.to_crs(epsg=22185)
    stops_proj = stops.to_crs(epsg=22185)
    counts = []
    for _, radio in radios_proj.iterrows():
        buf = radio.geometry.centroid.buffer(radius_m)
        n = len(stops_proj[stops_proj.geometry.within(buf)])
        counts.append(n)
    return pd.Series(counts, index=radios.index, name="transit_stops_500m")


def save_stops_caba() -> gpd.GeoDataFrame:
    gtfs = download_gtfs(GTFS_SUBTE_URL, "subte")
    stops_gdf = get_stops_geodataframe(gtfs)
    if stops_gdf.empty:
        logger.warning("No se pudieron extraer paradas del GTFS")
        return stops_gdf
    out = DATA_PROCESSED / "transport"
    out.mkdir(exist_ok=True)
    stops_gdf.to_file(out / "subte_stops.gpkg", driver="GPKG")
    logger.info(f"Paradas subte guardadas → {out / 'subte_stops.gpkg'}")
    return stops_gdf


if __name__ == "__main__":
    save_stops_caba()
