"""
INDEC Censo 2022 — radios censales y variables demográficas.
El shapefile de radios se descarga manualmente desde:
  https://www.indec.gob.ar/indec/web/Institucional-Indec-BasesDeDatos-5
Guardarlo en: data/raw/indec/radios_censales_2022.shp
"""
import geopandas as gpd
from loguru import logger
from shapely.geometry import box
from config import DATA_RAW, DATA_PROCESSED

INDEC_SHP = DATA_RAW / "indec" / "radios_censales_2022.shp"

INDEC_VARS = [
    "LINK",         # código único radio censal
    "PROV",         # provincia
    "DPTO",         # departamento/partido
    "FRAC",         # fracción censal
    "RADIO",        # radio
    "TOTAL_VIV",    # viviendas
    "TOTAL_HOG",    # hogares
    "TOTAL_POB",    # población total
]


def check_indec_available() -> bool:
    if not INDEC_SHP.exists():
        logger.warning(
            f"Shapefile INDEC no encontrado en {INDEC_SHP}\n"
            "Descargarlo de: https://www.indec.gob.ar/indec/web/Institucional-Indec-BasesDeDatos-5"
        )
        return False
    return True


def load_radios_bbox(bbox: tuple[float, float, float, float]) -> gpd.GeoDataFrame:
    """Carga radios censales dentro de un bounding box."""
    if not check_indec_available():
        return gpd.GeoDataFrame()
    gdf = gpd.read_file(INDEC_SHP, bbox=box(*bbox))
    gdf = gdf.to_crs(epsg=4326)
    logger.info(f"INDEC: {len(gdf)} radios censales cargados")
    return gdf


def save_radios_ciudad(ciudad_id: str, bbox: tuple) -> gpd.GeoDataFrame:
    gdf = load_radios_bbox(bbox)
    if gdf.empty:
        return gdf
    out = DATA_PROCESSED / "radios"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{ciudad_id}.gpkg"
    gdf.to_file(path, driver="GPKG")
    logger.info(f"Radios guardados → {path} ({len(gdf)} features)")
    return gdf


if __name__ == "__main__":
    from config import CIUDADES
    for ciudad_id, cfg in CIUDADES.items():
        save_radios_ciudad(ciudad_id, cfg["bbox"])
