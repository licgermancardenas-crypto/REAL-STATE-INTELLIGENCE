"""
Ingesta radios censales INDEC 2022.
Fuente: https://www.indec.gob.ar/indec/web/Institucional-Indec-BasesDeDatos-5
Descarga manual el shapefile de radios censales y ponelo en data/raw/indec/
Output: GeoPackage por ciudad en data/processed/radios/{city_id}.gpkg
"""
import geopandas as gpd
from loguru import logger
from shapely.geometry import box

from config import CITIES, RAW_DIR, PROCESSED_DIR

INDEC_SHP = RAW_DIR / "indec" / "radios_censales_2022.shp"


def filter_city(city_id: str) -> gpd.GeoDataFrame:
    city = CITIES[city_id]
    bbox = box(*city["bbox"])

    logger.info(f"Loading INDEC radios for {city['name']}")
    gdf = gpd.read_file(INDEC_SHP, bbox=bbox)
    gdf = gdf.to_crs(epsg=4326)

    out_path = PROCESSED_DIR / "radios" / f"{city_id}.gpkg"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(out_path, driver="GPKG")
    logger.info(f"  Saved {len(gdf)} radios → {out_path}")
    return gdf


if __name__ == "__main__":
    import sys
    city_id = sys.argv[1] if len(sys.argv) > 1 else "caba"
    filter_city(city_id)
