"""
Geocodifica listings de palermo_sample.csv con Nominatim (1 req/s),
hace spatial join contra caba_alpha_scores.geojson y calcula
correlación usd_m2 ↔ alpha_score.
"""
import re
import time
from pathlib import Path

import pandas as pd
import geopandas as gpd
import requests
from shapely.geometry import Point

ROOT    = Path(__file__).parent.parent
CSV_IN  = ROOT / "data/raw/precios/palermo_sample.csv"
GEOJSON = ROOT / "apps/web/public/caba_alpha_scores.geojson"
CSV_OUT = ROOT / "data/processed/palermo_alpha_join.csv"

NOMINATIM = "https://nominatim.openstreetmap.org/search"
HEADERS   = {"User-Agent": "RSI-research/1.0 (lic.germancardenas@gmail.com)"}
DELAY     = 1.1   # Nominatim: max 1 req/s

# CABA bounding box: left, top, right, bottom (lon_min, lat_max, lon_max, lat_min)
VIEWBOX   = "-58.533,-34.521,-58.334,-34.706"

# ── helpers ──────────────────────────────────────────────────────────────────

def clean_address(raw: str) -> str:
    """Elimina info de piso/unidad que confunde a Nominatim."""
    s = re.sub(r",?\s*[Pp]iso\s+\S+", "", raw)
    s = re.sub(r",?\s*\d+[°º][Pp]iso", "", s)
    s = re.sub(r"\s*,\s*$", "", s)          # coma final
    s = re.sub(r"\s{2,}", " ", s)           # espacios dobles
    # AV → Avenida al inicio (mejora hits en Nominatim)
    s = re.sub(r"^AV\b\.?\s*", "Avenida ", s, flags=re.IGNORECASE)
    return s.strip()

def geocode_one(address: str) -> tuple[float, float] | None:
    params = {
        "q":           f"{address}, Buenos Aires, Argentina",
        "format":      "json",
        "limit":       1,
        "countrycodes":"ar",
        "bounded":     1,
        "viewbox":     VIEWBOX,
    }
    try:
        r = requests.get(NOMINATIM, params=params, headers=HEADERS, timeout=10)
        r.raise_for_status()
        data = r.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception as exc:
        print(f"    ERROR: {exc}")
    return None

# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    # ── 1. Cargar y deduplicar CSV ──────────────────────────────────────────
    df = pd.read_csv(CSV_IN)
    before = len(df)
    df = df.drop_duplicates(subset="id_listing").reset_index(drop=True)
    print(f"Listings cargados: {before}  →  únicos: {len(df)}")

    df["m2"]        = pd.to_numeric(df["m2_cubiertos"], errors="coerce")
    df["precio_usd"] = pd.to_numeric(df["precio_usd"], errors="coerce")
    df["usd_m2"]    = (df["precio_usd"] / df["m2"]).round(0)

    # ── 2. Cargar GeoJSON radios CABA ───────────────────────────────────────
    gdf = gpd.read_file(GEOJSON).set_crs("EPSG:4326", allow_override=True)
    gdf["alpha_score"] = pd.to_numeric(gdf["alpha_score"], errors="coerce")
    print(f"Radios CABA: {len(gdf)}")

    # ── 3. Geocodificar ─────────────────────────────────────────────────────
    print(f"\nGeocoding {len(df)} direcciones (≈{len(df)*DELAY:.0f}s)…\n")
    lats, lons, statuses = [], [], []

    for i, row in df.iterrows():
        raw  = str(row["direccion"])
        addr = clean_address(raw)
        res  = geocode_one(addr)
        if res:
            lat, lon = res
            lats.append(lat); lons.append(lon); statuses.append("ok")
            print(f"  ✓ [{i+1:02d}] {addr}")
            print(f"        → ({lat:.5f}, {lon:.5f})")
        else:
            lats.append(None); lons.append(None); statuses.append("fail")
            print(f"  ✗ [{i+1:02d}] {addr}  ← FALLO")
        time.sleep(DELAY)

    df["lat"]    = lats
    df["lon"]    = lons
    df["geo_ok"] = statuses

    # ── 4. Spatial join ─────────────────────────────────────────────────────
    ok = df[df["geo_ok"] == "ok"].copy()
    gdf_pts = gpd.GeoDataFrame(
        ok,
        geometry=[Point(lon, lat) for lon, lat in zip(ok["lon"], ok["lat"])],
        crs="EPSG:4326",
    )

    joined = gpd.sjoin(
        gdf_pts,
        gdf[["link", "alpha_score", "alpha_quintil", "nearest_subte",
             "dist_subte_m", "geometry"]],
        how="left",
        predicate="within",
    )
    # sjoin puede duplicar si el punto cae en borde; tomar el primero
    joined = joined[~joined.index.duplicated(keep="first")]

    ok["radio_link"]    = joined["link"].values
    ok["alpha_score"]   = pd.to_numeric(joined["alpha_score"].values, errors="coerce")
    ok["alpha_quintil"] = joined["alpha_quintil"].values
    ok["nearest_subte"] = joined["nearest_subte"].values

    # Merge resultados al df original
    df = df.merge(
        ok[["id_listing", "radio_link", "alpha_score", "alpha_quintil", "nearest_subte"]],
        on="id_listing", how="left",
    )

    # ── 5. Tabla de resultados ──────────────────────────────────────────────
    W = 120
    print(f"\n{'═'*W}")
    print("TABLA: Listings × Alpha Score")
    print(f"{'═'*W}")

    display_ok = df[df["geo_ok"] == "ok"].copy()
    display_ok["alpha_score"] = display_ok["alpha_score"].apply(
        lambda x: f"{x:.1f}" if pd.notna(x) else "—"
    )
    display_ok["usd_m2_str"] = display_ok["usd_m2"].apply(
        lambda x: f"{int(x):,}" if pd.notna(x) else "—"
    )
    display_ok["m2_str"] = display_ok["m2"].apply(
        lambda x: f"{x:.0f}" if pd.notna(x) else "—"
    )

    # Header
    print(f"{'Dirección':<42} {'USD':>9} {'m²':>5} {'USD/m²':>7} {'Score':>6} {'Q':>2}  Radio")
    print(f"{'─'*42} {'─'*9} {'─'*5} {'─'*7} {'─'*6} {'─'*2}  {'─'*14}")

    for _, r in display_ok.iterrows():
        addr = str(r["direccion"])[:40]
        print(
            f"{addr:<42} "
            f"{int(r['precio_usd']):>9,} "
            f"{r['m2_str']:>5} "
            f"{r['usd_m2_str']:>7} "
            f"{r['alpha_score']:>6} "
            f"{str(r['alpha_quintil'])[:2]:>2}  "
            f"{str(r['radio_link'])[:14]}"
        )

    # ── 6. Correlación ──────────────────────────────────────────────────────
    corr_df = df[
        (df["geo_ok"] == "ok") &
        df["usd_m2"].notna() &
        df["alpha_score"].notna()
    ][["usd_m2", "alpha_score"]].copy()
    corr_df["alpha_score"] = pd.to_numeric(corr_df["alpha_score"], errors="coerce")

    print(f"\n{'─'*W}")
    print(f"CORRELACIÓN  usd_m2 ↔ alpha_score  (n={len(corr_df)} listings con m² conocido)")
    print(f"{'─'*W}")

    if len(corr_df) >= 3:
        r_pearson = corr_df["usd_m2"].corr(corr_df["alpha_score"])
        r_spearman = corr_df["usd_m2"].corr(corr_df["alpha_score"], method="spearman")
        print(f"  Pearson   r = {r_pearson:+.3f}")
        print(f"  Spearman  ρ = {r_spearman:+.3f}")
        print()
        if abs(r_pearson) >= 0.5:
            print(f"  → Correlación {'positiva' if r_pearson > 0 else 'negativa'} MODERADA-FUERTE: "
                  f"el Alpha Score {'anticipa bien' if r_pearson > 0 else 'invierte'} el precio/m².")
        elif abs(r_pearson) >= 0.25:
            print(f"  → Correlación {'positiva' if r_pearson > 0 else 'negativa'} DÉBIL: "
                  f"señal presente pero ruidosa. Sample chico (n={len(corr_df)}).")
        else:
            print(f"  → Sin correlación clara (r≈0). Causas posibles: "
                  f"outliers de precio, varianza de m² o sample pequeño.")

        # Mini tabla por quintil
        print(f"\n  Mediana usd/m² por quintil de Alpha Score:")
        print(f"  {'Quintil':>7}  {'Mediana USD/m²':>15}  {'n':>3}")
        df["alpha_score_num"] = pd.to_numeric(df["alpha_score"], errors="coerce")
        df["alpha_quintil_num"] = pd.to_numeric(df["alpha_quintil"], errors="coerce")
        for q in sorted(df["alpha_quintil_num"].dropna().unique()):
            sub = df[(df["alpha_quintil_num"] == q) & df["usd_m2"].notna()]
            if len(sub):
                print(f"  Q{int(q):>6}  {sub['usd_m2'].median():>15,.0f}  {len(sub):>3}")
    else:
        print(f"  Insuficientes datos con m² (n={len(corr_df)}). Necesitás al menos 3 listings con m².")

    # ── 7. Fallos de geocodificación ────────────────────────────────────────
    fails = df[df["geo_ok"] == "fail"]
    if len(fails):
        print(f"\n{'═'*W}")
        print(f"FALLOS DE GEOCODIFICACIÓN ({len(fails)} de {len(df)}):")
        print(f"{'─'*W}")
        for _, r in fails.iterrows():
            print(f"  ✗  {r['direccion']:<40}  USD {int(r['precio_usd']):>9,}")
    else:
        print(f"\n  ✓ Todas las {len(df)} direcciones geocodificaron correctamente.")

    # ── 8. Guardar CSV ──────────────────────────────────────────────────────
    CSV_OUT.parent.mkdir(parents=True, exist_ok=True)
    df.drop(columns=["geo_ok"], errors="ignore").to_csv(CSV_OUT, index=False)
    print(f"\n{'═'*W}")
    print(f"CSV guardado → {CSV_OUT}")

if __name__ == "__main__":
    main()
