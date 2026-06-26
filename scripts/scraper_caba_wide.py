"""
Scraper CABA-wide — sin filtro de barrio en URL.

Scrape departamentos en venta en Capital Federal, geocodifica con Nominatim
(reutiliza cache), y asigna barrio + Alpha Score via spatial join al final.

Uso:
  python scripts/scraper_caba_wide.py            # 20 páginas (~400 listings)
  python scripts/scraper_caba_wide.py --paginas 25
"""
import argparse
import json
import random
import re
import sys
import time
import warnings
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
from bs4 import BeautifulSoup
from scipy import stats as scipy_stats
from shapely.geometry import Point, shape

warnings.filterwarnings("ignore")

ROOT          = Path(__file__).parent.parent
DATA_RAW      = ROOT / "data/raw/precios"
DATA_PROC     = ROOT / "data/processed"
NOM_CACHE_F   = ROOT / "data/cache/nominatim_cache.json"
GCBA_F        = ROOT / "data/raw/geo/barrios_gcba.geojson"
GEOJSON_ALPHA = ROOT / "apps/web/public/caba_alpha_scores.geojson"
GCBA_URL      = "https://cdn.buenosaires.gob.ar/datosabiertos/datasets/ministerio-de-educacion/barrios/barrios.geojson"

AR_BASE     = "https://www.argenprop.com/departamento-en-venta--en-capital-federal"
PAGE_DELAY  = (9, 13)
GEO_DELAY   = 1.1
GEO_VIEWBOX = "-58.533,-34.521,-58.334,-34.706"
NOMINATIM   = "https://nominatim.openstreetmap.org/search"

AR_HDRS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://www.argenprop.com/",
}
NOM_HDRS = {"User-Agent": "RSI-research/1.0 (lic.germancardenas@gmail.com)"}

# ── Geocoding cache ───────────────────────────────────────────────────────────

def load_nom_cache() -> dict:
    NOM_CACHE_F.parent.mkdir(parents=True, exist_ok=True)
    if NOM_CACHE_F.exists():
        try:
            return json.loads(NOM_CACHE_F.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def save_nom_cache(cache: dict):
    NOM_CACHE_F.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")

# ── Address cleaning ──────────────────────────────────────────────────────────

def clean_address(raw: str) -> str:
    s = re.sub(r",?\s*[Pp]iso\s+\S+", "", raw)
    s = re.sub(r",?\s*\d+[°º][Pp]iso", "", s)
    s = re.sub(r"\s*,\s*$", "", s)
    s = re.sub(r"\s{2,}", " ", s)
    s = re.sub(r"^AV\.?\s+", "Avenida ", s, flags=re.IGNORECASE)
    return s.strip()

# ── Geocoding ─────────────────────────────────────────────────────────────────

def geocode(address: str, cache: dict) -> tuple[float, float] | None:
    key = address.lower().strip()
    if key in cache:
        return tuple(cache[key]) if cache[key] else None

    for bounded in (1, 0):
        params = {
            "q":            f"{address}, Buenos Aires, Argentina",
            "format":       "json",
            "limit":        1,
            "countrycodes": "ar",
            "bounded":      bounded,
        }
        if bounded:
            params["viewbox"] = GEO_VIEWBOX
        try:
            r = requests.get(NOMINATIM, params=params, headers=NOM_HDRS, timeout=10)
            r.raise_for_status()
            data = r.json()
            time.sleep(GEO_DELAY)
            if data:
                result = [float(data[0]["lat"]), float(data[0]["lon"])]
                cache[key] = result
                return tuple(result)
        except Exception as exc:
            print(f"    GEO ERROR: {exc}")
            time.sleep(GEO_DELAY)
            break

    cache[key] = None
    return None

# ── Argenprop page parser ─────────────────────────────────────────────────────

def extract_m2(items: list[str]) -> float | None:
    for item in items:
        m = re.search(r"(\d+[\.,]?\d*)\s*m", item, re.IGNORECASE)
        if m:
            try:
                return float(m.group(1).replace(",", "."))
            except ValueError:
                pass
    return None

def extract_ambientes(items: list[str], title: str) -> str:
    for item in items:
        if "ambiente" in item.lower() or "monoam" in item.lower():
            return item.strip()
    m = re.search(r"(\d)\s*ambiente|monoambiente", title, re.IGNORECASE)
    return m.group(0).strip() if m else ""

def parse_page(html: str) -> list[dict]:
    soup  = BeautifulSoup(html, "html.parser")
    cards = soup.find_all("a", attrs={"data-item-card": True})
    rows  = []
    for card in cards:
        if card.get("idmoneda") != "2":
            continue
        try:
            precio = int(card.get("montonormalizado", ""))
        except (ValueError, TypeError):
            continue
        if precio <= 0:
            continue

        feats     = card.find(class_="card__main-features")
        items     = [li.get_text(strip=True) for li in feats.find_all("li")] if feats else []
        title     = (card.find(class_="card__title") or card).get_text(strip=True)
        addr_el   = card.find(class_="card__address")
        direccion = addr_el.get_text(strip=True) if addr_el else ""
        href      = card.get("href", "")
        url       = f"https://www.argenprop.com{href}" if href.startswith("/") else href

        rows.append({
            "id_listing":  card.get("data-item-card", ""),
            "direccion":   direccion,
            "precio_usd":  precio,
            "m2":          extract_m2(items),
            "dormitorios": card.get("dormitorios", "").strip(),
            "ambientes":   extract_ambientes(items, title),
            "url_listing": url,
        })
    return rows

# ── Spatial joins ─────────────────────────────────────────────────────────────

def load_gcba_gdf() -> gpd.GeoDataFrame:
    if not GCBA_F.exists():
        print("Descargando polígonos GCBA…")
        r = requests.get(GCBA_URL, timeout=20)
        GCBA_F.parent.mkdir(parents=True, exist_ok=True)
        GCBA_F.write_bytes(r.content)
    return gpd.read_file(GCBA_F).set_crs("EPSG:4326", allow_override=True)

def assign_barrio_and_alpha(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    df = df.dropna(subset=["lat", "lon"]).reset_index(drop=True)

    gdf_pts = gpd.GeoDataFrame(
        df,
        geometry=[Point(r["lon"], r["lat"]) for _, r in df.iterrows()],
        crs="EPSG:4326",
    )

    # Join 1: GCBA barrios
    gdf_barrios = load_gcba_gdf()[["nombre", "geometry"]]
    joined_b = gpd.sjoin(gdf_pts, gdf_barrios, how="left", predicate="within")
    joined_b = joined_b[~joined_b.index.duplicated(keep="first")]
    df["barrio"] = joined_b["nombre"].values

    # Join 2: Alpha scores
    gdf_alpha = gpd.read_file(GEOJSON_ALPHA).set_crs("EPSG:4326", allow_override=True)
    gdf_alpha["alpha_score"]   = pd.to_numeric(gdf_alpha["alpha_score"],   errors="coerce")
    gdf_alpha["alpha_quintil"] = pd.to_numeric(gdf_alpha["alpha_quintil"], errors="coerce")

    gdf_pts2 = gpd.GeoDataFrame(
        df,
        geometry=[Point(r["lon"], r["lat"]) for _, r in df.iterrows()],
        crs="EPSG:4326",
    )
    joined_a = gpd.sjoin(
        gdf_pts2,
        gdf_alpha[["link", "alpha_score", "alpha_quintil", "geometry"]],
        how="left", predicate="within",
    )
    joined_a = joined_a[~joined_a.index.duplicated(keep="first")]
    df["radio_link"]    = joined_a["link"].values
    df["alpha_score"]   = joined_a["alpha_score"].values
    df["alpha_quintil"] = joined_a["alpha_quintil"].values
    return df

# ── Analysis ──────────────────────────────────────────────────────────────────

def print_barrio_distribution(df: pd.DataFrame):
    W = 72
    print(f"\n{'═'*W}")
    print(f"DISTRIBUCIÓN POR BARRIO GCBA  ({len(df)} listings geocodificados)")
    print(f"{'═'*W}")

    in_caba = df[df["barrio"].notna()]
    out_caba = df[df["barrio"].isna()]
    print(f"  Dentro de algún barrio GCBA : {len(in_caba)}")
    print(f"  Fuera de CABA / sin barrio  : {len(out_caba)}")

    if in_caba.empty:
        return

    by_barrio = (
        in_caba.groupby("barrio")
        .agg(
            n=("id_listing", "count"),
            med_usd_m2=("usd_m2", "median"),
            med_alpha=("alpha_score", "median"),
        )
        .sort_values("n", ascending=False)
        .reset_index()
    )

    print(f"\n  {'Barrio':<22} {'n':>4}  {'Med.USD/m²':>11}  {'Med.Alpha':>10}")
    print(f"  {'─'*22} {'─'*4}  {'─'*11}  {'─'*10}")
    for _, r in by_barrio.iterrows():
        usd_str   = f"${r['med_usd_m2']:,.0f}" if pd.notna(r["med_usd_m2"]) else "—"
        alpha_str = f"{r['med_alpha']:.1f}"   if pd.notna(r["med_alpha"])   else "—"
        print(f"  {str(r['barrio']):<22} {int(r['n']):>4}  {usd_str:>11}  {alpha_str:>10}")

    covered = by_barrio[by_barrio["n"] >= 5]
    print(f"\n  Barrios con ≥5 listings: {len(covered)}/{len(by_barrio)}")

    # Correlation if we have enough spread
    sub = in_caba[in_caba["usd_m2"].notna() & in_caba["alpha_score"].notna()].copy()
    sub["alpha_score"] = pd.to_numeric(sub["alpha_score"], errors="coerce")
    sub = sub.dropna(subset=["alpha_score"])
    n = len(sub)

    if n >= 20:
        print(f"\n{'═'*W}")
        print(f"CORRELACIÓN usd_m2 ↔ alpha_score  (n={n} con m² conocido)")
        print(f"{'═'*W}")
        r_p, p_val = scipy_stats.pearsonr(sub["usd_m2"], sub["alpha_score"])
        r_s, p_s   = scipy_stats.spearmanr(sub["usd_m2"], sub["alpha_score"])
        print(f"  Pearson  r  = {r_p:+.4f}  (p={p_val:.4f})")
        print(f"  Spearman rho= {r_s:+.4f}  (p={p_s:.4f})")

        sig = "p<0.01 — MUY SIGNIFICATIVA" if p_val < 0.01 else \
              "p<0.05 — significativa" if p_val < 0.05 else \
              f"p={p_val:.2f} — no significativa"
        print(f"  → {sig}")

        print(f"\n  Mediana USD/m² por quintil Alpha:")
        print(f"  {'Q':>2}  {'Mediana':>9}  {'n':>4}  {'Barrios top'}")
        print(f"  {'─'*2}  {'─'*9}  {'─'*4}  {'─'*35}")
        for q in sorted(sub["alpha_quintil"].dropna().unique()):
            seg = sub[sub["alpha_quintil"] == q]
            top_b = seg.groupby("barrio")["usd_m2"].count().sort_values(ascending=False)
            barrios_str = ", ".join(f"{b}({c})" for b, c in top_b.head(3).items())
            print(f"  Q{int(q):>1}  {seg['usd_m2'].median():>9,.0f}  {len(seg):>4}  {barrios_str}")
    else:
        print(f"\n  n={n} con m² conocido — correlación disponible con más datos.")

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--paginas",      type=int, default=20)
    parser.add_argument("--desde-pagina", type=int, default=1,
                        help="Página inicial (para continuar un lote previo)")
    parser.add_argument("--lote",         type=str, default="1",
                        help="Sufijo del archivo de salida (lote1, lote2, …)")
    args = parser.parse_args()

    DATA_RAW.mkdir(parents=True, exist_ok=True)
    DATA_PROC.mkdir(parents=True, exist_ok=True)

    p_desde = args.desde_pagina
    p_hasta = p_desde + args.paginas - 1
    print(f"CABA-wide scraper — páginas {p_desde}–{p_hasta}  (lote {args.lote})")
    nom_cache = load_nom_cache()
    print(f"Cache Nominatim: {len(nom_cache)} entradas")

    session = requests.Session()
    session.headers.update(AR_HDRS)

    seen_ids  = set()
    all_rows: list[dict] = []
    geo_ok    = 0
    geo_fail  = 0
    cache_saved = len(nom_cache)

    for page_num in range(p_desde, p_hasta + 1):

        if page_num > 1:
            delay = random.uniform(*PAGE_DELAY)
            print(f"\nEsperando {delay:.1f}s…")
            time.sleep(delay)

        url = AR_BASE if page_num == 1 else f"{AR_BASE}--pagina-{page_num}"
        print(f"GET pág {page_num:>2}: {url}")

        try:
            resp = session.get(url, timeout=25)
        except requests.exceptions.Timeout:
            print("TIMEOUT — fin del scraping.")
            break
        except requests.exceptions.ConnectionError as e:
            print(f"CONNECTION ERROR: {e} — fin del scraping.")
            break

        print(f"  HTTP {resp.status_code} | {len(resp.content):,} bytes", end="")

        if resp.status_code in (403, 429):
            print(f"\nBLOQUEO ({resp.status_code}) — parando.")
            break
        if resp.status_code != 200:
            print(f"\nStatus {resp.status_code} inesperado — abortando.")
            break

        cards = parse_page(resp.text)
        if not cards:
            print(" — sin listings, fin de resultados.")
            break

        print(f" | {len(cards)} cards")

        new_this = 0
        for row in cards:
            lid = row["id_listing"]
            if lid in seen_ids:
                continue
            seen_ids.add(lid)

            raw_addr = str(row["direccion"]).strip()
            if not raw_addr:
                geo_fail += 1
                continue

            addr_clean = clean_address(raw_addr)
            coords = geocode(addr_clean, nom_cache)

            if coords is None:
                geo_fail += 1
                continue

            lat, lon = coords
            usd_m2   = round(row["precio_usd"] / row["m2"]) if row["m2"] else None
            all_rows.append({**row, "lat": lat, "lon": lon, "usd_m2": usd_m2})
            geo_ok  += 1
            new_this += 1

        print(f"  +{new_this} geocodificados | total={geo_ok} | fallos={geo_fail}")

        # Persist cache every 50 new entries
        if len(nom_cache) >= cache_saved + 50:
            save_nom_cache(nom_cache)
            cache_saved = len(nom_cache)

    save_nom_cache(nom_cache)

    if not all_rows:
        print("Sin datos. Abortando.")
        sys.exit(1)

    print(f"\n{geo_ok} listings geocodificados. Asignando barrios + Alpha Scores…")
    df = assign_barrio_and_alpha(all_rows)

    out_raw  = DATA_RAW  / f"caba_wide_lote{args.lote}.csv"
    out_proc = DATA_PROC / f"caba_wide_lote{args.lote}_alpha.csv"
    df.to_csv(out_raw,  index=False, encoding="utf-8")
    df.to_csv(out_proc, index=False, encoding="utf-8")
    print(f"Guardado: {out_raw}")
    print(f"Guardado: {out_proc}")

    print_barrio_distribution(df)

    print(f"\n{'='*72}")
    print(f"FIN  |  total listings: {len(df)}"
          f"  |  con barrio GCBA: {df['barrio'].notna().sum()}"
          f"  |  con alpha: {df['alpha_score'].notna().sum()}"
          f"  |  cache Nominatim: {len(nom_cache)} entradas")

if __name__ == "__main__":
    main()
