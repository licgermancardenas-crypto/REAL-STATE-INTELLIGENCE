"""
Validación Opción B — NBI en scoring CABA.

Compara scores v1 (sin NBI) vs v2 (con NBI) para:
  - Cobertura del dato NBI
  - Top/bottom movers
  - Palermo, Puerto Madero, Villa Lugano (radios individuales)

No toca los archivos de producción — solo imprime resultados.

Uso:
  python scripts/validate_nbi_option_b.py
"""
import json
import math
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

from models.scoring import (
    WEIGHTS_V1, WEIGHTS_V2,
    load_all_pois, build_radio_features, load_nbi_data,
    _minmax,
)

DATA_PROCESSED = ROOT / "data" / "processed"
DATA_RAW       = ROOT / "data" / "raw"


def _compute_scores(df: gpd.GeoDataFrame, weights: dict) -> pd.Series:
    """Calcula score a partir de features ya normalizadas."""
    return (sum(df[feat] * w for feat, w in weights.items()) * 100).round(1)


def _get_barrio_radios(
    radios_df: gpd.GeoDataFrame,
    barrios_geojson: Path,
    barrio_name: str,
) -> gpd.GeoDataFrame:
    """Intersecta radios con el polígono del barrio para encontrar cuáles pertenecen."""
    barrios = gpd.read_file(barrios_geojson).to_crs("EPSG:4326")
    match = barrios[barrios["nombre"].str.lower() == barrio_name.lower()]
    if match.empty:
        raise ValueError(f"Barrio no encontrado: {barrio_name}")
    barrio_poly = match.geometry.union_all()
    radios_wgs = radios_df.to_crs("EPSG:4326")
    centroids  = radios_wgs.geometry.centroid
    mask = centroids.within(barrio_poly)
    return radios_df[mask].copy()


def main():
    print("=" * 65)
    print("  VALIDACIÓN OPCIÓN B — NBI EN ALPHA SCORE CABA")
    print("=" * 65)

    # ── 1. Cargar datos ───────────────────────────────────────────────
    print("\n[1/4] Cargando datos ...")
    radios = gpd.read_file(DATA_PROCESSED / "census" / "caba_radios.gpkg")
    radios = radios[radios.geometry.is_valid & ~radios.geometry.is_empty].copy()
    print(f"  Radios CABA: {len(radios)}")

    stops_raw = gpd.read_file(DATA_PROCESSED / "transport" / "subte_stops.gpkg")
    stops_raw["stop_lat"] = pd.to_numeric(stops_raw["stop_lat"], errors="coerce")
    stops_raw["stop_lon"] = pd.to_numeric(stops_raw["stop_lon"], errors="coerce")
    stops_raw = stops_raw.dropna(subset=["stop_lat", "stop_lon"])
    stops = gpd.GeoDataFrame(
        stops_raw,
        geometry=gpd.points_from_xy(stops_raw["stop_lon"], stops_raw["stop_lat"]),
        crs="EPSG:4326",
    )

    # ── 2. NBI coverage ──────────────────────────────────────────────
    print("\n[2/4] Cargando NBI ...")
    nbi_series = load_nbi_data(radios)
    if nbi_series is None:
        print("  ERROR: BA Data NBI no encontrado")
        return

    n_with_data = nbi_series.notna().sum()
    print(f"\n  Cobertura NBI: {n_with_data}/{len(radios)} radios "
          f"({n_with_data/len(radios)*100:.1f}%)")
    print(f"  pct_sin_nbi — min: {nbi_series.min():.3f} | "
          f"mediana: {nbi_series.median():.3f} | "
          f"media: {nbi_series.mean():.3f} | "
          f"max: {nbi_series.max():.3f}")

    # Distribución NBI
    bins = [0, 0.80, 0.90, 0.95, 0.98, 1.0]
    labels = ["<80% sin NBI (alto NBI)", "80-90%", "90-95%", "95-98%", ">98% sin NBI"]
    dist = pd.cut(nbi_series, bins=bins, labels=labels)
    print("\n  Distribución pct_sin_nbi:")
    for label, cnt in dist.value_counts().sort_index().items():
        pct = cnt / len(radios) * 100
        bar = "#" * int(pct / 2)
        print(f"    {label:<25} {cnt:4d} radios ({pct:4.1f}%) {bar}")

    # ── 3. Features + scores ─────────────────────────────────────────
    print("\n[3/4] Calculando features y scores ...")
    pois   = load_all_pois(DATA_PROCESSED / "osm")
    scored = build_radio_features(radios, pois, stops, nbi_series=nbi_series)

    # Normalizar (igual que compute_alpha_score)
    scored["poi_total_density_norm"]         = _minmax(scored["poi_total_density"])
    scored["div_entropy_ex_transporte_norm"] = _minmax(scored["div_entropy_ex_transporte"])
    scored["poi_espacios_verdes_norm"]       = _minmax(scored["poi_espacios_verdes_density"])
    scored["densidad_pob_norm"]              = _minmax(scored["densidad_pob"])
    scored["poi_educacion_norm"]             = _minmax(scored["poi_educacion_density"])
    scored["poi_salud_norm"]                 = _minmax(scored["poi_salud_density"])
    scored["dist_subte_score"]               = 1.0 - _minmax(scored["dist_subte_m"])
    scored["nbi_score_norm"]                 = _minmax(scored["pct_sin_nbi"])

    scored["score_v1"] = _compute_scores(scored, WEIGHTS_V1)
    scored["score_v2"] = _compute_scores(scored, WEIGHTS_V2)
    scored["delta"]    = (scored["score_v2"] - scored["score_v1"]).round(1)

    print(f"\n  Score v1 — media: {scored['score_v1'].mean():.1f} | "
          f"mediana: {scored['score_v1'].median():.1f}")
    print(f"  Score v2 — media: {scored['score_v2'].mean():.1f} | "
          f"mediana: {scored['score_v2'].median():.1f}")
    print(f"  Delta medio: {scored['delta'].mean():.2f} | "
          f"std: {scored['delta'].std():.2f}")

    # Top 10 que más suben y bajan
    print("\n  Top 10 radios que más SUBEN con NBI (zonas con muchos hogares sin NBI):")
    top_up = scored.nlargest(10, "delta")[
        ["link", "score_v1", "score_v2", "delta", "pct_sin_nbi", "poi_total_density"]
    ]
    print(top_up.to_string(index=False))

    print("\n  Top 10 radios que más BAJAN con NBI (zonas con alta NBI):")
    top_down = scored.nsmallest(10, "delta")[
        ["link", "score_v1", "score_v2", "delta", "pct_sin_nbi", "poi_total_density"]
    ]
    print(top_down.to_string(index=False))

    # ── 4. Barrios objetivo ──────────────────────────────────────────
    print("\n[4/4] Análisis por barrio objetivo ...")
    barrios_geojson = DATA_RAW / "gcba" / "barrios_caba.geojson"
    for barrio in ["Palermo", "Puerto Madero", "Villa Lugano"]:
        try:
            subset = _get_barrio_radios(scored, barrios_geojson, barrio)
            n = len(subset)
            if n == 0:
                print(f"\n  {barrio}: 0 radios encontrados")
                continue
            print(f"\n  ── {barrio.upper()} ({n} radios) ──")
            print(f"  Score v1: {subset['score_v1'].mean():.1f} ± {subset['score_v1'].std():.1f} "
                  f"  [min {subset['score_v1'].min():.1f} — max {subset['score_v1'].max():.1f}]")
            print(f"  Score v2: {subset['score_v2'].mean():.1f} ± {subset['score_v2'].std():.1f} "
                  f"  [min {subset['score_v2'].min():.1f} — max {subset['score_v2'].max():.1f}]")
            print(f"  Delta   : {subset['delta'].mean():.2f} ± {subset['delta'].std():.2f}")
            print(f"  pct_sin_nbi media: {subset['pct_sin_nbi'].mean():.3f}")
            print(f"  poi_total_density media: {subset['poi_total_density'].mean():.1f} POIs/km²")
            print()
            # Mostrar top 5 radios del barrio
            cols_show = ["link", "score_v1", "score_v2", "delta",
                         "pct_sin_nbi", "poi_total_density", "dist_subte_m"]
            top5 = subset.nlargest(5, "score_v2")[cols_show]
            print("  Top 5 radios por score_v2:")
            print("  " + top5.to_string(index=False).replace("\n", "\n  "))
        except Exception as e:
            print(f"\n  ERROR en {barrio}: {e}")

    print("\n" + "=" * 65)
    print("  CONCLUSIÓN:")
    n_up   = (scored["delta"] > 0.5).sum()
    n_down = (scored["delta"] < -0.5).sum()
    n_same = len(scored) - n_up - n_down
    print(f"  {n_up} radios suben > 0.5 pts | "
          f"{n_same} sin cambio significativo | "
          f"{n_down} bajan > 0.5 pts")
    print("=" * 65)


if __name__ == "__main__":
    main()
