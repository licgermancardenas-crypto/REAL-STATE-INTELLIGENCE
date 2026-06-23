"""
Pipeline CABA — descarga, clip y features para los 48 barrios.

Para cada barrio en barrios_caba.geojson:
  1. Bbox desde el poligono real (+ padding de 300m)
  2. Descarga POIs Overpass (6 cats) con cache por categoria:
       - Si el JSON ya existe → lo saltea
       - Si faltan algunas cats → descarga solo las faltantes
  3. Clip al poligono real del barrio (clip_pois)
  4. Features: densidades, subte, diversidad, div_ex_transporte

Los DataFrames de barrios y subte se cargan UNA vez y se reutilizan
en los 48 pasos para evitar re-leer disco.

Timing estimado (primer run, sin cache):
  ~10s/categoria (5s kumi timeout + 5s maps.mail.ru + 3s sleep + overhead)
  47 barrios x 6 cats x ~10s = ~47 min
  Palermo ya cacheado: 47 barrios restantes

Uso:
  python src/pipeline/caba_full.py               # corre todo
  python src/pipeline/caba_full.py --skip-done   # solo barrios sin clean dir
"""
import json
import re
import sys
import time
import unicodedata
from pathlib import Path

import geopandas as gpd
import pandas as pd
from loguru import logger
from tqdm import tqdm

# ── Path setup ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent.parent
_ingesta = ROOT / "src" / "ingesta"
_utils   = ROOT / "src" / "utils"
_models  = ROOT / "src" / "models"
for p in [str(_ingesta), str(_utils), str(_models)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from overpass import fetch_pois, POI_CATEGORIES  # noqa: E402
from clip_pois import clip_pois                  # noqa: E402
from feature_engineering import build_barrio_features  # noqa: E402

# ── Paths ─────────────────────────────────────────────────────────────────────
DATA_RAW        = ROOT / "data" / "raw"
DATA_PROCESSED  = ROOT / "data" / "processed"
BARRIOS_GEOJSON = DATA_RAW / "gcba" / "barrios_caba.geojson"
SUBTE_STOPS     = DATA_PROCESSED / "transport" / "subte_stops.gpkg"
FEATURES_OUT    = DATA_PROCESSED / "features"

BBOX_PAD = 0.003   # ~300m extra around polygon bounds to catch edge POIs


# ── Helpers ───────────────────────────────────────────────────────────────────

def _slugify(name: str) -> str:
    """'Nuñez' → 'nunez', 'Villa Gral. Mitre' → 'villa_gral_mitre'"""
    name = unicodedata.normalize('NFKD', name)
    name = ''.join(c for c in name if not unicodedata.combining(c))
    name = name.lower()
    name = re.sub(r'[^a-z0-9\s]', '', name)
    name = re.sub(r'\s+', '_', name.strip())
    return name


def _bbox_from_polygon(polygon) -> tuple:
    b = polygon.bounds  # (minx, miny, maxx, maxy)
    return (b[0] - BBOX_PAD, b[1] - BBOX_PAD, b[2] + BBOX_PAD, b[3] + BBOX_PAD)


def _missing_categories(osm_dir: Path) -> list:
    """Devuelve las categorias sin JSON descargado."""
    return [cat for cat in POI_CATEGORIES if not (osm_dir / f"{cat}.json").exists()]


def _missing_clean(clean_dir: Path) -> list:
    """Devuelve las categorias sin GPKG clippeado."""
    return [cat for cat in POI_CATEGORIES if not (clean_dir / f"{cat}.gpkg").exists()]


def _save_pois_partial(ciudad_id: str, bbox: tuple, categories: list) -> None:
    """Descarga solo las categorias faltantes y las guarda como JSON."""
    pois = fetch_pois(bbox, categories)
    out  = DATA_RAW / "osm" / ciudad_id
    out.mkdir(parents=True, exist_ok=True)
    for cat, elements in pois.items():
        path = out / f"{cat}.json"
        path.write_text(
            json.dumps({"elements": elements}, ensure_ascii=False),
            encoding="utf-8",
        )


# ── Per-barrio pipeline ───────────────────────────────────────────────────────

def process_barrio(
    nombre: str,
    polygon,
    barrios_gdf: gpd.GeoDataFrame,
    stops_gdf: gpd.GeoDataFrame,
    skip_done: bool = False,
) -> pd.DataFrame | None:
    """
    Ejecuta las 3 fases para un barrio: download → clip → features.
    Retorna el DataFrame de features, o None si hubo error.
    """
    slug      = _slugify(nombre)
    ciudad_id = f"caba_{slug}"
    osm_dir   = DATA_RAW  / "osm" / ciudad_id
    clean_dir = DATA_PROCESSED / "osm" / f"{ciudad_id}_clean"

    # ── Fase 1: Download (con cache por categoria) ────────────────────────────
    missing_cats = _missing_categories(osm_dir)
    if missing_cats:
        bbox = _bbox_from_polygon(polygon)
        logger.info(f"[{nombre}] Descargando {len(missing_cats)} cats: {missing_cats}")
        try:
            _save_pois_partial(ciudad_id, bbox, missing_cats)
        except Exception as e:
            logger.error(f"[{nombre}] Overpass falló: {e}")
            return None
    else:
        logger.info(f"[{nombre}] POIs en cache — saltando descarga")

    # ── Fase 2: Clip ─────────────────────────────────────────────────────────
    missing_gpkg = _missing_clean(clean_dir)
    if missing_gpkg:
        logger.info(f"[{nombre}] Clipeando {len(missing_gpkg)} cats")
        try:
            clip_pois(nombre, osm_dir)
        except Exception as e:
            logger.error(f"[{nombre}] Clip falló: {e}")
            return None
    else:
        logger.info(f"[{nombre}] Clip en cache — saltando")

    # ── Fase 3: Features ──────────────────────────────────────────────────────
    try:
        df = build_barrio_features(
            barrio=nombre,
            ciudad_id="caba",
            barrios_gdf=barrios_gdf,
            stops_gdf=stops_gdf,
        )
        return df
    except Exception as e:
        logger.error(f"[{nombre}] Features fallaron: {e}")
        return None


# ── Main ──────────────────────────────────────────────────────────────────────

def run(skip_done: bool = False) -> pd.DataFrame:
    logger.info("=== Pipeline CABA full — 48 barrios ===")

    barrios_gdf = gpd.read_file(BARRIOS_GEOJSON).to_crs("EPSG:4326")
    stops_gdf   = gpd.read_file(SUBTE_STOPS)
    barrios     = barrios_gdf.sort_values("nombre").reset_index(drop=True)

    # Tiempo estimado: ~10s por categoria, 6 cats, N barrios sin cache
    already_done = sum(
        1 for _, r in barrios.iterrows()
        if not _missing_categories(DATA_RAW / "osm" / f"caba_{_slugify(r['nombre'])}")
    )
    todo = len(barrios) - already_done
    logger.info(f"  {already_done}/48 barrios ya en cache | {todo} por descargar")
    if todo > 0:
        est_min = todo * 6 * 10 / 60
        logger.info(f"  Estimado descarga: ~{est_min:.0f} min (timeout 5s kumi + 5s maps.mail.ru + 3s sleep)")

    results   = []
    errors    = []
    t_start   = time.time()

    for _, row in tqdm(barrios.iterrows(), total=len(barrios), desc="Barrios CABA"):
        nombre  = row["nombre"]
        polygon = row.geometry

        df = process_barrio(
            nombre=nombre,
            polygon=polygon,
            barrios_gdf=barrios_gdf,
            stops_gdf=stops_gdf,
            skip_done=skip_done,
        )
        if df is not None:
            results.append(df)
        else:
            errors.append(nombre)

    elapsed = (time.time() - t_start) / 60
    logger.info(f"\nPipeline completado en {elapsed:.1f} min")
    logger.info(f"  OK: {len(results)} barrios | Errores: {len(errors)}")
    if errors:
        logger.warning(f"  Con error: {errors}")

    if not results:
        raise RuntimeError("Sin resultados — revisar logs de error")

    full_df = pd.concat(results, ignore_index=True)

    FEATURES_OUT.mkdir(parents=True, exist_ok=True)
    out_path = FEATURES_OUT / "caba_full_features.csv"
    full_df.to_csv(out_path, index=False)
    logger.info(f"Guardado: {out_path}  ({len(full_df)} filas x {len(full_df.columns)} cols)")

    return full_df


def print_ranking(df: pd.DataFrame, top_n: int | None = None) -> None:
    """Tabla de barrios ordenada por densidad total de POIs."""
    df_sorted = df.sort_values("poi_total_density", ascending=False).reset_index(drop=True)
    if top_n:
        df_sorted = df_sorted.head(top_n)

    sep = "-" * 82
    print(f"\n{'Ranking CABA — POI total density (post-clip)'}")
    print(sep)
    print(
        f"{'#':>3}  {'Barrio':<22}  {'Area':>6}  "
        f"{'Total/km2':>9}  {'Transp':>6}  {'Edu':>5}  "
        f"{'Ofi':>5}  {'Salud':>5}  {'Subte_m':>7}  {'H_ex_t':>6}"
    )
    print(sep)
    for i, r in df_sorted.iterrows():
        print(
            f"{i+1:>3}  {r['barrio']:<22}  {r['area_km2']:>6.2f}  "
            f"{r['poi_total_density']:>9.1f}  "
            f"{r['poi_transporte_density']:>6.1f}  "
            f"{r['poi_educacion_density']:>5.1f}  "
            f"{r['poi_oficinas_density']:>5.1f}  "
            f"{r['poi_salud_density']:>5.1f}  "
            f"{r['dist_subte_m']:>7.0f}  "
            f"{r['div_entropy_ex_transporte']:>6.3f}"
        )
    print(sep)
    print(f"  H_ex_t = Shannon normalizado sin transporte (0=mono, 1=diverso)")


if __name__ == "__main__":
    skip = "--skip-done" in sys.argv
    df   = run(skip_done=skip)
    print_ranking(df)
