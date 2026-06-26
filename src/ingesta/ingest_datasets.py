"""
Ingesta de datasets externos al proyecto.

Datasets procesados:
  1. ar.csv (SimpleMaps)         → data/raw/simplemaps/ar.csv
  2. Codgeo_CABA_con_datos.zip   → data/processed/census/caba_radios.gpkg
     3555 radios CABA + datos censales (POB, HOGARES, VIV)
  3. capas_unidades_geoestadisticas/capa_radios_censales.zip
                                  → data/raw/indec/radios_censales.gpkg
     66515 radios nacionales (solo geometria + cod_indec)
  4. radios-censales.geojson     → data/raw/bsas/radios_censales.gpkg
     23901 radios Buenos Aires provincia (GBA) con LINK

Uso:
  python src/ingesta/ingest_datasets.py
"""
import io
import os
import shutil
import sys
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
from loguru import logger

ROOT           = Path(__file__).parent.parent.parent
DATA_RAW       = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
DOWNLOADS      = Path(r"C:\Users\corra\Downloads")

# ── 1. ar.csv ─────────────────────────────────────────────────────────────────

def ingest_simplemaps():
    src = DOWNLOADS / "ar.csv"
    dst_dir = DATA_RAW / "simplemaps"
    dst = dst_dir / "ar.csv"
    if not src.exists():
        logger.error(f"No encontrado: {src}")
        return
    dst_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    df = pd.read_csv(dst)
    logger.info(f"SimpleMaps ar.csv → {dst}  ({len(df)} ciudades)")


# ── 2. Codgeo_CABA_con_datos.zip ──────────────────────────────────────────────

def ingest_caba_radios():
    src = DOWNLOADS / "Codgeo_CABA_con_datos.zip"
    if not src.exists():
        logger.error(f"No encontrado: {src}")
        return

    tmp = Path(r"C:\Users\corra\AppData\Local\Temp\caba_codgeo")
    if tmp.exists():
        shutil.rmtree(tmp)
    with zipfile.ZipFile(src) as z:
        z.extractall(tmp)

    shp = tmp / "cabaxrdatos.shp"
    gdf = gpd.read_file(shp)
    logger.info(f"  CABA radios raw: {len(gdf)} filas | CRS: {gdf.crs}")

    # Reproyectar a WGS84 para consistencia con el resto del proyecto
    gdf = gdf.to_crs("EPSG:4326")

    # Renombrar columnas a snake_case legible
    gdf = gdf.rename(columns={
        "PROV":       "prov",
        "DEPTO":      "depto",
        "FRAC":       "frac",
        "RADIO":      "radio",
        "TIPO":       "tipo",
        "LINK":       "link",
        "VARONES":    "varones",
        "MUJERES":    "mujeres",
        "TOT_POB":    "tot_pob",
        "HOGARES":    "hogares",
        "VIV_PART":   "viv_part",
        "VIV_PART_H": "viv_part_h",
    })

    # Eliminar columnas técnicas del shapefile
    drop = [c for c in gdf.columns if c in ("AREA", "PERIMETER", "PAIS0210_", "PAIS0210_I")]
    gdf = gdf.drop(columns=drop, errors="ignore")

    dst_dir = DATA_PROCESSED / "census"
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / "caba_radios.gpkg"
    gdf.to_file(dst, driver="GPKG")
    logger.info(f"CABA radios → {dst}  ({len(gdf)} radios, {len(gdf.columns)} cols)")
    logger.info(f"  Cols: {list(gdf.columns)}")
    logger.info(f"  Poblacion total CABA: {int(gdf['tot_pob'].sum()):,}")


# ── 3. capa_radios_censales (INDEC nacional) ──────────────────────────────────

def ingest_indec_radios():
    src = DOWNLOADS / "capas_unidades_geoestadisticas (1).zip"
    if not src.exists():
        logger.error(f"No encontrado: {src}")
        return

    tmp = Path(r"C:\Users\corra\AppData\Local\Temp\indec_radios")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)

    with zipfile.ZipFile(src) as outer:
        inner_bytes = outer.read("capa_radios_censales.zip")
    with zipfile.ZipFile(io.BytesIO(inner_bytes)) as inner:
        inner.extractall(tmp)

    shp = tmp / "radios_censales.shp"
    gdf = gpd.read_file(shp)
    logger.info(f"  INDEC radios raw: {len(gdf)} filas | CRS: {gdf.crs}")

    # Reproyectar a WGS84
    gdf = gdf.to_crs("EPSG:4326")

    # Renombrar columnas a nombres claros
    gdf = gdf.rename(columns={
        "id":        "id",
        "cpr":       "cod_prov",
        "jur":       "provincia",
        "cde":       "cod_depto",
        "dpto":      "departamento",
        "cfn":       "fraccion",
        "cro":       "radio",
        "tro":       "tipo",
        "cod_indec": "link",
        "sag":       "fuente",
    })

    dst_dir = DATA_RAW / "indec"
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / "radios_censales.gpkg"
    gdf.to_file(dst, driver="GPKG")
    logger.info(f"INDEC radios nacionales → {dst}  ({len(gdf)} radios)")
    logger.info(f"  Cols: {list(gdf.columns)}")
    by_prov = gdf.groupby("provincia").size().sort_values(ascending=False)
    logger.info(f"  Top 5 provincias:\n{by_prov.head(5).to_string()}")


# ── 4. radios-censales.geojson (Buenos Aires provincia / GBA) ─────────────────

def ingest_bsas_radios():
    src = Path(r"C:\Users\corra\Downloads\radios_2022_tmp\radios-censales.geojson")
    if not src.exists():
        logger.error(f"No encontrado: {src}")
        return

    gdf = gpd.read_file(src)
    logger.info(f"  GBA radios raw: {len(gdf)} filas | CRS: {gdf.crs}")

    # Ya en EPSG:4326; renombrar a snake_case
    gdf = gdf.rename(columns={
        "fid":       "fid",
        "AREA":      "area_m2",
        "PERIMETER": "perimeter_m",
        "NOMPROV":   "provincia",
        "PROV":      "cod_prov",
        "NOMDEPTO":  "departamento",
        "DEPTO":     "cod_depto",
        "FRAC":      "fraccion",
        "RADIO":     "radio",
        "TIPO":      "tipo",
        "LINK":      "link",
    })

    dst_dir = DATA_RAW / "bsas"
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / "radios_censales.gpkg"
    gdf.to_file(dst, driver="GPKG")
    logger.info(f"GBA radios → {dst}  ({len(gdf)} radios)")
    logger.info(f"  Cols: {list(gdf.columns)}")
    logger.info(f"  Departamentos sample: {sorted(gdf['departamento'].unique())[:8]}")


# ── 5. Codgeo Buenos Aires con datos (Censo 2010) ─────────────────────────────

def ingest_pba_radios():
    """
    Descarga Codgeo_Buenos_Aires_con_datos.zip desde INDEC si no existe,
    y procesa el shapefile a data/processed/census/pba_radios.gpkg.

    Columnas fuente: toponimo_i, link, varon, mujer, totalpobl,
                     hogares, viviendasp, viv_part_h
    """
    local_zip = DOWNLOADS / "Codgeo_Buenos_Aires_con_datos.zip"
    url = "https://www.indec.gob.ar/ftp/cuadros/territorio/codgeo/Codgeo_Buenos_Aires_con_datos.zip"

    if not local_zip.exists():
        logger.info("  Descargando Codgeo_Buenos_Aires_con_datos.zip desde INDEC ...")
        import httpx
        with httpx.stream("GET", url, timeout=120, follow_redirects=True) as r:
            r.raise_for_status()
            with open(local_zip, "wb") as f:
                for chunk in r.iter_bytes(chunk_size=65536):
                    f.write(chunk)
        logger.info(f"  Descargado: {local_zip.stat().st_size:,} bytes")

    tmp = Path(r"C:\Users\corra\AppData\Local\Temp\pba_codgeo")
    if tmp.exists():
        shutil.rmtree(tmp)
    with zipfile.ZipFile(local_zip) as z:
        z.extractall(tmp)

    shp = next(tmp.glob("*.shp"))
    gdf = gpd.read_file(shp)
    logger.info(f"  PBA radios raw: {len(gdf)} filas | CRS: {gdf.crs}")

    gdf = gdf.to_crs("EPSG:4326")

    gdf = gdf.rename(columns={
        "toponimo_i": "toponimo_id",
        "link":       "link",
        "varon":      "varones",
        "mujer":      "mujeres",
        "totalpobl":  "tot_pob",
        "hogares":    "hogares",
        "viviendasp": "viv_part",
        "viv_part_h": "viv_part_h",
    })

    dst_dir = DATA_PROCESSED / "census"
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / "pba_radios.gpkg"
    gdf.to_file(dst, driver="GPKG")

    tot = int(gdf["tot_pob"].sum())
    logger.info(f"PBA radios → {dst}  ({len(gdf)} radios)")
    logger.info(f"  Cols: {list(gdf.columns)}")
    logger.info(f"  Poblacion total PBA (Censo 2010): {tot:,}")
    logger.info(f"  Radios con datos (tot_pob > 0): {int((gdf['tot_pob'] > 0).sum())}")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    targets = sys.argv[1:] or ["all"]

    if "all" in targets or "simplemaps" in targets:
        logger.info("--- 1. SimpleMaps ar.csv ---")
        ingest_simplemaps()
    if "all" in targets or "caba" in targets:
        logger.info("--- 2. CABA radios con datos censales ---")
        ingest_caba_radios()
    if "all" in targets or "indec" in targets:
        logger.info("--- 3. INDEC radios nacionales ---")
        ingest_indec_radios()
    if "all" in targets or "bsas" in targets:
        logger.info("--- 4. GBA radios geometria (Buenos Aires prov) ---")
        ingest_bsas_radios()
    if "all" in targets or "pba" in targets:
        logger.info("--- 5. PBA radios con datos censales ---")
        ingest_pba_radios()
    logger.info("=== Ingesta completa ===")
