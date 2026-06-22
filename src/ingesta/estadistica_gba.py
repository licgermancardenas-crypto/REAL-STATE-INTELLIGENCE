"""
Estadística GBA — Dirección Provincial de Estadística, Provincia de Buenos Aires.

Fuentes:
  - Cartografía Censal 2022 GBA:
    https://cartografiacensal-2022.estadistica.ec.gba.gov.ar/index.php/mapoteca/censo-2022/
  - Shapefiles descargables:
    https://mapas.estadistica.ec.gba.gov.ar/portal/apps/sites/#/mapas-estadisticos/pages/descargas-shapes
  - Portal estadístico:
    https://www.estadistica.ec.gba.gov.ar/

NOTA: Los shapefiles se descargan manualmente desde el portal.
Este módulo asume que los archivos están en data/raw/estadistica_gba/
y los procesa/estandariza para el pipeline de scoring.

Estructura esperada en data/raw/estadistica_gba/:
  radios_censales_gba_2022.shp  (o .zip con shapefile)
  partidos_gba.shp
  localidades_gba.shp
"""
import zipfile
from pathlib import Path
import geopandas as gpd
import pandas as pd
from loguru import logger
from config import DATA_RAW, DATA_PROCESSED, PARTIDOS_GBA

GBA_RAW_DIR = DATA_RAW / "estadistica_gba"
GBA_PROCESSED_DIR = DATA_PROCESSED / "gba"


def _find_shp(directory: Path, pattern: str) -> Path | None:
    matches = list(directory.glob(f"**/{pattern}"))
    return matches[0] if matches else None


def _extract_zip_if_needed(zip_path: Path) -> Path:
    extract_dir = zip_path.parent / zip_path.stem
    if not extract_dir.exists():
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(extract_dir)
        logger.info(f"Extraído: {zip_path.name} → {extract_dir}")
    return extract_dir


def load_radios_gba(partido: str | None = None) -> gpd.GeoDataFrame:
    """
    Carga radios censales GBA 2022 desde el shapefile local.
    partido: nombre del partido para filtrar (ej: 'La Matanza').
             None = todos los 24 partidos.
    """
    GBA_RAW_DIR.mkdir(parents=True, exist_ok=True)

    # Buscar shapefile (puede venir en zip o directo)
    zip_files = list(GBA_RAW_DIR.glob("*.zip"))
    for z in zip_files:
        _extract_zip_if_needed(z)

    shp = _find_shp(GBA_RAW_DIR, "radios*.shp") or _find_shp(GBA_RAW_DIR, "*.shp")
    if not shp:
        logger.warning(
            "Shapefile radios GBA no encontrado.\n"
            f"Descargarlo desde:\n"
            f"  https://cartografiacensal-2022.estadistica.ec.gba.gov.ar/index.php/mapoteca/censo-2022/\n"
            f"Guardar en: {GBA_RAW_DIR}"
        )
        return gpd.GeoDataFrame()

    gdf = gpd.read_file(shp)
    gdf = gdf.to_crs(epsg=4326)

    if partido:
        col_partido = next(
            (c for c in gdf.columns if "partido" in c.lower() or "dpto" in c.lower()), None
        )
        if col_partido:
            gdf = gdf[gdf[col_partido].str.contains(partido, case=False, na=False)]

    logger.info(f"Radios GBA cargados: {len(gdf)} features" + (f" (partido: {partido})" if partido else ""))
    return gdf


def save_radios_por_partido() -> dict[str, Path]:
    """Divide el shapefile GBA en archivos por partido y los guarda como GPKG."""
    gdf = load_radios_gba()
    if gdf.empty:
        return {}

    GBA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    col_partido = next(
        (c for c in gdf.columns if "partido" in c.lower() or "dpto" in c.lower()), None
    )
    if not col_partido:
        logger.error("No se encontró columna de partido en el shapefile GBA")
        return {}

    saved = {}
    for partido in gdf[col_partido].unique():
        subset = gdf[gdf[col_partido] == partido]
        slug = partido.lower().replace(" ", "_").replace(".", "")
        path = GBA_PROCESSED_DIR / f"radios_{slug}.gpkg"
        subset.to_file(path, driver="GPKG")
        saved[partido] = path

    logger.info(f"Guardados {len(saved)} partidos → {GBA_PROCESSED_DIR}")
    return saved


def load_indicadores_socioeconomicos() -> pd.DataFrame:
    """
    Carga indicadores socioeconómicos por partido desde Estadística GBA.
    El CSV/Excel se descarga manualmente desde:
      https://www.estadistica.ec.gba.gov.ar/
    Guardar en: data/raw/estadistica_gba/indicadores_socioeconomicos.csv
    """
    path = GBA_RAW_DIR / "indicadores_socioeconomicos.csv"
    if not path.exists():
        logger.warning(f"Archivo no encontrado: {path}")
        return pd.DataFrame()
    df = pd.read_csv(path, encoding="latin-1")
    logger.info(f"Indicadores GBA: {len(df)} filas, {len(df.columns)} columnas")
    return df


if __name__ == "__main__":
    gdf = load_radios_gba()
    if not gdf.empty:
        print(gdf.columns.tolist())
        print(gdf.head(3))
