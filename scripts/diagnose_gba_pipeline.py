"""
Diagnóstico post-pipeline GBA.
Muestra:
  1. Partidos con datos completos vs. faltantes
  2. POI counts por partido
  3. Preview de scoring para partidos conocidos (con centroide para identificarlos)
  4. Si el scoring completo es posible, lo corre y muestra stats por partido

Uso:
  python scripts/diagnose_gba_pipeline.py
"""
import sys
import json
import math
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "ingesta"))

import geopandas as gpd
import numpy as np
import pandas as pd

DATA_RAW       = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
CONURBANO_BBOX = (-59.1, -35.1, -58.2, -34.3)
MIN_RADIOS     = 50
POI_CATEGORIES = ["comercio", "educacion", "espacios_verdes", "oficinas", "salud", "transporte"]

# INDEC PBA depto code → partido name (subset conocidos)
CODIGO_PARTIDO = {
    # Confirmed by centroid coordinates (see scripts/map_depto_coords.py)
    "027": "La Matanza",      # fallback
    "028": "Almirante Brown",   # -34.82, -58.37 ✓
    "035": "Avellaneda",        # -34.68, -58.35 ✓
    "091": "Berazategui",       # -34.78, -58.23 ✓
    "134": "Berisso/sur",       # -35.01, -58.72 (La Plata area)
    "252": "Escobar/norte",     # -34.38, -58.77 (north, NOT Ensenada)
    "260": "Esteban Echeverría",# -34.81, -58.47 ✓
    "270": "Ezeiza/sur",        # -34.88, -58.55
    "274": "sur-costero",       # -34.82, -58.27 (coastal south)
    "364": "noroeste ext.",     # -34.62, -58.94 (far west)
    "371": "Gral San Martín",   # -34.56, -58.56 ✓
    "408": "Hurlingham",        # -34.60, -58.64 ✓
    "410": "Ituzaingó",         # -34.64, -58.69 ✓
    "412": "José C. Paz",       # -34.52, -58.77 ✓
    "427": "La Matanza",        # -34.72, -58.58 ✓ (confirmed by size)
    "434": "Lanús",             # -34.71, -58.40 ✓
    "490": "Lomas de Zamora",   # -34.75, -58.42 ✓
    "515": "MalvArg/norte",     # -34.49, -58.71
    "525": "noroeste/sur",      # -34.78, -58.83
    "539": "Merlo",             # -34.69, -58.73 ✓
    "560": "Moreno",            # -34.62, -58.79 ✓ (NOT Quilmes!)
    "568": "Morón",             # -34.65, -58.62 ✓ (NOT Pte Perón)
    "638": "noroeste ext2",     # -34.46, -58.86
    "648": "sur ext.",          # -34.92, -58.39 (NOT San Isidro!)
    "658": "Quilmes",           # -34.74, -58.28 ✓ (NOT San Miguel)
    "749": "San Fernando",      # -34.45, -58.56 ✓
    "756": "San Isidro",        # -34.49, -58.54 ✓ (NOT Tres de Febrero!)
    "760": "Malvinas Arg.",     # -34.56, -58.72
    "778": "sur ext2",          # -35.01, -58.40
    "805": "Tigre/delta",       # -34.44, -58.64
    "840": "Tres de Febrero",   # -34.60, -58.57 ✓
    "861": "Vicente López",     # -34.52, -58.50 ✓ (NOT Pilar!)
}


def get_conurbano_radios():
    pba = gpd.read_file(DATA_PROCESSED / "census" / "pba_radios.gpkg").to_crs("EPSG:4326")
    lon_min, lat_min, lon_max, lat_max = CONURBANO_BBOX
    cx = pba.geometry.centroid.x
    cy = pba.geometry.centroid.y
    mask = (cx >= lon_min) & (cx <= lon_max) & (cy >= lat_min) & (cy <= lat_max)
    c = pba[mask].copy()
    c["depto_code"] = c["link"].str[2:5]
    c["centroid_lon"] = cx[mask].values
    c["centroid_lat"] = cy[mask].values
    return c


def survey_poi_data(deptos: dict) -> pd.DataFrame:
    """Para cada depto, cuenta POIs en el directorio _clean."""
    rows = []
    for code, n_radios in sorted(deptos.items(), key=lambda x: -x[1]):
        clean_dir = DATA_PROCESSED / "osm" / f"gba_{code}_clean"
        raw_dir   = DATA_RAW / "osm" / f"gba_{code}"

        raw_exists   = raw_dir.exists()
        clean_exists = clean_dir.exists()

        poi_counts = {}
        if clean_exists:
            for cat in POI_CATEGORIES:
                gpkg = clean_dir / f"{cat}.gpkg"
                if gpkg.exists():
                    try:
                        gdf = gpd.read_file(gpkg)
                        poi_counts[cat] = len(gdf)
                    except Exception:
                        poi_counts[cat] = -1
                else:
                    poi_counts[cat] = None  # missing

        n_complete = sum(1 for v in poi_counts.values() if v is not None and v >= 0)
        status = "OK COMPLETO" if n_complete == 6 else (
                 f"~~ PARCIAL ({n_complete}/6)" if n_complete > 0 else (
                 "DL RAW ONLY" if raw_exists else "XX FALTANTE"))

        rows.append({
            "depto_code":  code,
            "nombre":      CODIGO_PARTIDO.get(code, f"?{code}"),
            "n_radios":    n_radios,
            "status":      status,
            "n_cats_ok":   n_complete,
            **{f"n_{cat}": poi_counts.get(cat, 0) or 0 for cat in POI_CATEGORIES},
        })

    return pd.DataFrame(rows)


def _minmax(s: pd.Series) -> pd.Series:
    lo, hi = s.min(), s.max()
    return pd.Series(0.5, index=s.index) if hi == lo else (s - lo) / (hi - lo)


def _shannon_h(row, cats):
    counts = [row[f"poi_{c}_count"] for c in cats if row.get(f"poi_{c}_count", 0) > 0]
    if len(counts) < 2:
        return 0.0
    total = sum(counts)
    probs = [c / total for c in counts]
    h = -sum(p * math.log(p) for p in probs)
    return round(h / math.log(len(counts)), 4)


def run_preview_scoring(conurbano: gpd.GeoDataFrame, survey: pd.DataFrame) -> pd.DataFrame:
    """
    Corre scoring completo para los partidos con datos, agrega por depto.
    """
    from models.scoring_gba import (
        _minmax, _shannon_h, load_gba_pois, extract_rail_stations,
        build_gba_features, compute_gba_score, WEIGHTS_V1_GBA, CRS_METRIC
    )

    pois     = load_gba_pois()
    if not pois:
        print("Sin datos POI procesados aún.")
        return pd.DataFrame()

    stations = extract_rail_stations(pois)
    scored   = build_gba_features(conurbano, pois, stations)
    scored   = compute_gba_score(scored, full_mode=True)

    # Agregar por partido
    scored["depto_code"] = scored["link"].str[2:5]
    agg = scored.groupby("depto_code").agg(
        n_radios       = ("link", "count"),
        score_mean     = ("alpha_score", "mean"),
        score_median   = ("alpha_score", "median"),
        score_max      = ("alpha_score", "max"),
        score_min      = ("alpha_score", "min"),
        poi_density    = ("poi_total_density", "mean"),
        entropy        = ("div_entropy_ex_transporte", "mean"),
        dist_tren_med  = ("dist_tren_m", "median"),
        densidad_pob   = ("densidad_pob", "mean"),
    ).reset_index()
    agg["nombre"] = agg["depto_code"].map(CODIGO_PARTIDO).fillna("?")
    return agg


def main():
    print("=" * 70)
    print("  DIAGNÓSTICO PIPELINE GBA")
    print("=" * 70)

    conurbano = get_conurbano_radios()
    deptos_counts = conurbano.groupby("depto_code").size().to_dict()
    deptos_big = {k: v for k, v in deptos_counts.items() if v >= MIN_RADIOS}

    # ── 1. Tabla de estado ─────────────────────────────────────────────────
    print("\n[1/3] Estado de datos POI por partido\n")
    survey = survey_poi_data(deptos_big)

    n_completo = (survey["n_cats_ok"] == 6).sum()
    n_parcial  = ((survey["n_cats_ok"] > 0) & (survey["n_cats_ok"] < 6)).sum()
    n_faltante = (survey["n_cats_ok"] == 0).sum()

    print(f"  Partidos con POI completo (6/6 cats): {n_completo}/{len(survey)}")
    print(f"  Parcial (1-5 cats):                   {n_parcial}/{len(survey)}")
    print(f"  Sin datos POI:                        {n_faltante}/{len(survey)}")
    total_radios_ok = survey.loc[survey["n_cats_ok"] == 6, "n_radios"].sum()
    total_radios    = survey["n_radios"].sum()
    print(f"  Radios cubiertos (full):              {total_radios_ok}/{total_radios} "
          f"({total_radios_ok/total_radios*100:.1f}%)")
    print()

    # Tabla compacta
    print(f"  {'Código':<6} {'Partido':<24} {'Radios':>6} {'Status':<20} "
          f"{'comercio':>8} {'transp':>6} {'educ':>5} {'salud':>5} {'verde':>5} {'ofic':>4}")
    print("  " + "-" * 88)
    for _, row in survey.sort_values("n_radios", ascending=False).iterrows():
        print(f"  {row['depto_code']:<6} {row['nombre']:<24} {row['n_radios']:>6}  "
              f"{row['status']:<20} "
              f"{row['n_comercio']:>8} {row['n_transporte']:>6} {row['n_educacion']:>5} "
              f"{row['n_salud']:>5} {row['n_espacios_verdes']:>5} {row['n_oficinas']:>4}")

    # ── 2. Centroides para identificar partidos ────────────────────────────
    print("\n[2/3] Centroides por partido (para identificación geográfica)\n")
    centroids = conurbano.groupby("depto_code").agg(
        lat=("centroid_lat", "mean"),
        lon=("centroid_lon", "mean"),
        n_radios=("link", "count"),
    ).reset_index()
    centroids["nombre"] = centroids["depto_code"].map(CODIGO_PARTIDO).fillna("?")
    centroids = centroids.sort_values("n_radios", ascending=False)

    print(f"  {'Código':<6} {'Partido':<24} {'Radios':>6} {'Lat':>8} {'Lon':>9}")
    print("  " + "-" * 57)
    for _, row in centroids.iterrows():
        if row["n_radios"] >= MIN_RADIOS:
            print(f"  {row['depto_code']:<6} {row['nombre']:<24} {row['n_radios']:>6}  "
                  f"{row['lat']:>8.4f} {row['lon']:>9.4f}")

    # ── 3. Scoring preview ─────────────────────────────────────────────────
    complete_deptos = survey[survey["n_cats_ok"] == 6]["depto_code"].tolist()
    print(f"\n[3/3] Preview scoring ({len(complete_deptos)} partidos con datos completos)\n")

    if len(complete_deptos) < 3:
        print("  Insuficientes datos para scoring aún. Re-correr cuando termine el pipeline.")
        return

    try:
        agg = run_preview_scoring(conurbano[conurbano["depto_code"].isin(complete_deptos)], survey)
        if agg.empty:
            print("  Scoring falló (ver log).")
            return

        print(f"  {'Código':<6} {'Partido':<24} {'Radios':>6} {'Mediana':>8} {'Media':>6} "
              f"{'Max':>5} {'POIs/km²':>9} {'Dist tren':>10}")
        print("  " + "-" * 80)
        for _, row in agg.sort_values("score_median", ascending=False).iterrows():
            print(f"  {row['depto_code']:<6} {row['nombre']:<24} {row['n_radios']:>6}  "
                  f"{row['score_median']:>7.1f} {row['score_mean']:>6.1f} "
                  f"{row['score_max']:>5.1f} {row['poi_density']:>9.1f} {row['dist_tren_med']:>10.0f} m")

        # Focus: San Isidro, La Matanza, Quilmes
        print("\n  ── PARTIDOS OBJETIVO ──")
        TARGET_CODES = {"427": "La Matanza", "756": "San Isidro",  "658": "Quilmes",
                        "861": "Vicente López", "840": "Tres de Febrero",
                        "434": "Lanús", "035": "Avellaneda", "490": "Lomas de Zamora"}
        for code, name in TARGET_CODES.items():
            row = agg[agg["depto_code"] == code]
            if row.empty:
                # Check if it's in our complete list
                if code in complete_deptos:
                    print(f"  {name} ({code}): en datos pero no en scoring")
                else:
                    print(f"  {name} ({code}): sin datos aún")
                continue
            r = row.iloc[0]
            print(f"  {r['nombre']:<24} ({r['depto_code']})  "
                  f"mediana={r['score_median']:.1f}  media={r['score_mean']:.1f}  "
                  f"max={r['score_max']:.1f}  POIs/km²={r['poi_density']:.1f}  "
                  f"dist_tren={r['dist_tren_med']:.0f}m")

    except Exception as e:
        print(f"  ERROR en scoring: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
