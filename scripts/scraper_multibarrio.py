"""
Multi-barrio scraper — filtro GCBA en-vuelo + join Alpha Score.

Pipeline:
  1. Palermo    → carga palermo_v2.csv existente (62 listings ya filtrados)
  2. Caballito  → scraping fresco, filtro polígono GCBA, target 60
  3. Flores     → scraping fresco, filtro polígono GCBA, target 50
  4. Villa Lugano → scraping fresco, filtro polígono GCBA, target 35
  5. Spatial join Alpha Score sobre el dataset unificado
  6. Correlación usd_m2 ↔ alpha_score + tabla resumen por barrio

Uso:
  python scripts/scraper_multibarrio.py
"""
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
GEO_CACHE_F   = ROOT / "data/raw/geo/barrios_gcba.geojson"
NOM_CACHE_F   = ROOT / "data/cache/nominatim_cache.json"
GEOJSON_ALPHA = ROOT / "apps/web/public/caba_alpha_scores.geojson"
GCBA_URL      = "https://cdn.buenosaires.gob.ar/datosabiertos/datasets/ministerio-de-educacion/barrios/barrios.geojson"
NOMINATIM     = "https://nominatim.openstreetmap.org/search"

PAGE_DELAY  = (9, 13)
GEO_DELAY   = 1.1
GEO_VIEWBOX = "-58.533,-34.521,-58.334,-34.706"

AR_HDRS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://www.argenprop.com/",
}
NOM_HDRS = {"User-Agent": "RSI-research/1.0 (lic.germancardenas@gmail.com)"}

BARRIOS = [
    {
        "nombre":         "palermo",
        "gcba_nombre":    "Palermo",
        "argenprop_slug": "palermo",
        "target":         60,
        "max_pages":      30,
        "existing_csv":   ROOT / "data/raw/precios/palermo_v2.csv",
    },
    {
        "nombre":         "caballito",
        "gcba_nombre":    "Caballito",
        "argenprop_slug": "caballito",
        "target":         60,
        "max_pages":      30,
        "existing_csv":   None,
    },
    {
        "nombre":         "flores",
        "gcba_nombre":    "Flores",
        "argenprop_slug": "flores",
        "target":         50,
        "max_pages":      25,
        "existing_csv":   None,
    },
    {
        "nombre":         "villa-lugano",
        "gcba_nombre":    "Villa Lugano",
        "argenprop_slug": "villa-lugano",
        "target":         35,
        "max_pages":      20,
        "existing_csv":   None,
    },
]

# ── GCBA polygons ─────────────────────────────────────────────────────────────

def load_gcba_polygons() -> dict:
    """Return {gcba_nombre_lower: shapely polygon}."""
    if not GEO_CACHE_F.exists():
        print("Descargando polígonos GCBA…")
        r = requests.get(GCBA_URL, timeout=20)
        GEO_CACHE_F.parent.mkdir(parents=True, exist_ok=True)
        GEO_CACHE_F.write_bytes(r.content)
    data = json.loads(GEO_CACHE_F.read_text(encoding="utf-8"))
    return {
        f["properties"]["nombre"].lower(): shape(f["geometry"])
        for f in data["features"]
    }

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

        feats    = card.find(class_="card__main-features")
        items    = [li.get_text(strip=True) for li in feats.find_all("li")] if feats else []
        title    = (card.find(class_="card__title") or card).get_text(strip=True)
        addr_el  = card.find(class_="card__address")
        direccion = addr_el.get_text(strip=True) if addr_el else ""
        href     = card.get("href", "")
        url      = f"https://www.argenprop.com{href}" if href.startswith("/") else href

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

# ── Per-barrio scraper ────────────────────────────────────────────────────────

def scrape_barrio(cfg: dict, polygon, nom_cache: dict, session: requests.Session) -> list[dict]:
    nombre   = cfg["nombre"]
    slug     = cfg["argenprop_slug"]
    target   = cfg["target"]
    max_pgs  = cfg["max_pages"]
    base_url = f"https://www.argenprop.com/departamento-en-venta--en-{slug}"
    out_csv  = DATA_RAW / f"{nombre}.csv"

    print(f"\n{'─'*70}")
    print(f"BARRIO: {nombre.upper()} | target={target} | max_pages={max_pgs}")
    print(f"{'─'*70}")

    seen_ids      = set()
    ok_rows       = []
    rejected_total = 0
    save_every    = 10   # persist geocoding cache every N new listings

    for page_num in range(1, max_pgs + 1):

        if len(ok_rows) >= target:
            print(f"\nTarget alcanzado ({len(ok_rows)}). Siguiente barrio.")
            break

        if page_num > 1:
            delay = random.uniform(*PAGE_DELAY)
            print(f"\nEsperando {delay:.1f}s antes de pág. {page_num}…")
            time.sleep(delay)

        url = base_url if page_num == 1 else f"{base_url}--pagina-{page_num}"
        print(f"GET {url}")

        try:
            resp = session.get(url, timeout=25)
        except requests.exceptions.Timeout:
            print("TIMEOUT — abortando barrio.")
            break
        except requests.exceptions.ConnectionError as e:
            print(f"CONNECTION ERROR: {e} — abortando barrio.")
            break

        print(f"  HTTP {resp.status_code} | {len(resp.content):,} bytes")

        if resp.status_code in (403, 429):
            print(f"BLOQUEO ({resp.status_code}) — parando.")
            break
        if resp.status_code != 200:
            print(f"Status {resp.status_code} inesperado — abortando.")
            break

        cards = parse_page(resp.text)
        if not cards:
            print("  Sin listings — fin de resultados.")
            break

        new_this = 0
        prev_cache_size = len(nom_cache)

        for row in cards:
            lid = row["id_listing"]
            if lid in seen_ids:
                continue
            seen_ids.add(lid)

            raw_addr = str(row["direccion"]).strip()
            if not raw_addr:
                rejected_total += 1
                continue

            addr_clean = clean_address(raw_addr)
            coords = geocode(addr_clean, nom_cache)

            if coords is None:
                print(f"  GEO FAIL: {raw_addr[:55]}")
                rejected_total += 1
                continue

            lat, lon = coords
            pt = Point(lon, lat)

            if polygon.contains(pt):
                usd_m2 = round(row["precio_usd"] / row["m2"]) if row["m2"] else None
                ok_rows.append({
                    "barrio":     nombre,
                    **row,
                    "lat":        lat,
                    "lon":        lon,
                    "usd_m2":    usd_m2,
                })
                new_this += 1
                print(
                    f"  OK [{len(ok_rows):>3}] {raw_addr[:50]:<50}"
                    f" ({lat:.5f},{lon:.5f})"
                )
            else:
                rejected_total += 1

        # Persist geocoding cache when new entries added
        if len(nom_cache) > prev_cache_size:
            save_nom_cache(nom_cache)

        print(
            f"  Pág {page_num}: +{new_this} OK | total OK={len(ok_rows)}"
            f" | rechazados acum.={rejected_total}"
        )

    # Save per-barrio CSV
    if ok_rows:
        pd.DataFrame(ok_rows).to_csv(out_csv, index=False, encoding="utf-8")
        print(f"  Guardado: {out_csv}  ({len(ok_rows)} listings)")
    else:
        print(f"  Sin datos para {nombre}.")

    save_nom_cache(nom_cache)
    return ok_rows

# ── Load from existing CSV ────────────────────────────────────────────────────

def load_existing(path: Path, barrio_nombre: str) -> list[dict]:
    df = pd.read_csv(path, encoding="utf-8")
    df["barrio"] = barrio_nombre
    rows = df.to_dict(orient="records")
    print(f"\nCargado desde CSV: {path.name}  ({len(rows)} listings de {barrio_nombre})")
    return rows

# ── Alpha score spatial join ──────────────────────────────────────────────────

def assign_alpha(all_rows: list[dict]) -> pd.DataFrame:
    gdf_radios = gpd.read_file(GEOJSON_ALPHA).set_crs("EPSG:4326", allow_override=True)
    gdf_radios["alpha_score"]   = pd.to_numeric(gdf_radios["alpha_score"],   errors="coerce")
    gdf_radios["alpha_quintil"] = pd.to_numeric(gdf_radios["alpha_quintil"], errors="coerce")

    df = pd.DataFrame(all_rows)
    # coerce lat/lon to numeric (loaded from CSV they might be strings)
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    df = df.dropna(subset=["lat", "lon"]).reset_index(drop=True)

    gdf_pts = gpd.GeoDataFrame(
        df,
        geometry=[Point(r["lon"], r["lat"]) for _, r in df.iterrows()],
        crs="EPSG:4326",
    )
    joined = gpd.sjoin(
        gdf_pts,
        gdf_radios[["link", "alpha_score", "alpha_quintil", "geometry"]],
        how="left",
        predicate="within",
    )
    joined = joined[~joined.index.duplicated(keep="first")]
    df["radio_link"]    = joined["link"].values
    df["alpha_score"]   = joined["alpha_score"].values
    df["alpha_quintil"] = joined["alpha_quintil"].values
    return df

# ── Analysis: correlation + barrio summary ────────────────────────────────────

def print_analysis(df: pd.DataFrame):
    W = 72
    sep = "═" * W

    # ── Barrio summary table ──────────────────────────────────────────────
    print(f"\n{sep}")
    print("TABLA RESUMEN POR BARRIO")
    print(sep)
    print(
        f"{'Barrio':<14} {'n':>4}  {'Med.USD/m²':>11}  "
        f"{'Med.Alpha':>10}  {'Q dom.':>7}  {'Avg.Alpha':>10}"
    )
    print("─" * W)

    barrio_order = ["palermo", "caballito", "flores", "villa-lugano"]
    rows_list = []
    for b in barrio_order:
        sub = df[df["barrio"] == b].copy()
        sub_ok = sub[sub["usd_m2"].notna() & sub["alpha_score"].notna()].copy()
        if sub_ok.empty:
            continue
        med_usd = sub_ok["usd_m2"].median()
        avg_usd = sub_ok["usd_m2"].mean()
        med_alpha = sub_ok["alpha_score"].median()
        avg_alpha = sub_ok["alpha_score"].mean()
        q_dom = int(sub_ok["alpha_quintil"].mode().iloc[0]) if not sub_ok["alpha_quintil"].isna().all() else "?"
        print(
            f"{b:<14} {len(sub_ok):>4}  {med_usd:>11,.0f}  "
            f"{med_alpha:>10.1f}  {'Q'+str(q_dom):>7}  {avg_alpha:>10.1f}"
        )
        rows_list.append({
            "barrio": b, "n": len(sub_ok),
            "med_usd_m2": med_usd, "avg_usd_m2": avg_usd,
            "med_alpha": med_alpha, "avg_alpha": avg_alpha,
        })

    # ── Correlation on unified dataset ────────────────────────────────────
    sub_all = df[df["usd_m2"].notna() & df["alpha_score"].notna()].copy()
    sub_all["alpha_score"] = pd.to_numeric(sub_all["alpha_score"], errors="coerce")
    sub_all = sub_all[sub_all["alpha_score"].notna()]
    n = len(sub_all)

    print(f"\n{sep}")
    print(f"CORRELACIÓN CROSS-BARRIO  usd_m2 ↔ alpha_score  (n={n})")
    print(sep)

    if n < 10:
        print(f"  Insuficientes datos (n={n}).")
        return

    r_p, p_val = scipy_stats.pearsonr(sub_all["usd_m2"], sub_all["alpha_score"])
    r_s, p_s   = scipy_stats.spearmanr(sub_all["usd_m2"], sub_all["alpha_score"])

    print(f"  Pearson  r  = {r_p:+.4f}  (p={p_val:.4f})")
    print(f"  Spearman rho= {r_s:+.4f}  (p={p_s:.4f})")
    print()

    if p_val < 0.01:
        sig = "muy significativa (p<0.01)"
    elif p_val < 0.05:
        sig = "significativa (p<0.05)"
    else:
        sig = f"NO significativa (p={p_val:.2f})"

    direction = "positiva" if r_p > 0 else "negativa"
    strength  = "fuerte" if abs(r_p) >= 0.6 else "moderada" if abs(r_p) >= 0.35 else "débil"
    print(f"  Interpretación: correlación {direction} {strength} — {sig}.")

    # ── Per-barrio correlation ────────────────────────────────────────────
    print(f"\n  Correlación Pearson por barrio:")
    for b in barrio_order:
        sub_b = sub_all[sub_all["barrio"] == b]
        if len(sub_b) < 5:
            continue
        r_b, p_b = scipy_stats.pearsonr(sub_b["usd_m2"], sub_b["alpha_score"])
        print(f"    {b:<14}  r={r_b:+.3f}  p={p_b:.3f}  n={len(sub_b)}")

    # ── Scatter por quintil ───────────────────────────────────────────────
    print(f"\n  Mediana usd/m² por quintil Alpha (dataset unificado):")
    print(f"  {'Q':>2}  {'Mediana USD/m²':>15}  {'n':>5}  {'Barrios principales'}")
    print(f"  {'─'*2}  {'─'*15}  {'─'*5}  {'─'*30}")
    for q in sorted(sub_all["alpha_quintil"].dropna().unique()):
        seg = sub_all[sub_all["alpha_quintil"] == q]
        barrios_q = seg.groupby("barrio")["usd_m2"].count().sort_values(ascending=False)
        barrios_str = ", ".join(f"{b}({c})" for b, c in barrios_q.head(3).items())
        print(
            f"  Q{int(q):>1}  {seg['usd_m2'].median():>15,.0f}  "
            f"{len(seg):>5}  {barrios_str}"
        )

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    DATA_PROC.mkdir(parents=True, exist_ok=True)

    print("Cargando polígonos GCBA…")
    polygons = load_gcba_polygons()

    print("Cargando cache de geocodificación…")
    nom_cache = load_nom_cache()
    print(f"  {len(nom_cache)} entradas en caché.")

    session = requests.Session()
    session.headers.update(AR_HDRS)

    all_rows: list[dict] = []

    for cfg in BARRIOS:
        gcba_key = cfg["gcba_nombre"].lower()
        polygon  = polygons.get(gcba_key)
        if polygon is None:
            print(f"ADVERTENCIA: polígono '{cfg['gcba_nombre']}' no encontrado en GCBA. Saltando.")
            continue

        if cfg["existing_csv"] and Path(cfg["existing_csv"]).exists():
            rows = load_existing(Path(cfg["existing_csv"]), cfg["nombre"])
        else:
            rows = scrape_barrio(cfg, polygon, nom_cache, session)

        all_rows.extend(rows)

    if not all_rows:
        print("Sin datos. Abortando.")
        sys.exit(1)

    # Final save of geocoding cache
    save_nom_cache(nom_cache)

    print(f"\nTotal listings: {len(all_rows)}")
    print("Asignando Alpha Scores via spatial join…")
    df = assign_alpha(all_rows)

    # Save unified CSV
    out_unified = DATA_PROC / "cross_barrio_alpha.csv"
    df.to_csv(out_unified, index=False, encoding="utf-8")
    print(f"Guardado: {out_unified}")

    print_analysis(df)

    print(f"\n{'='*72}")
    print("FIN DEL PIPELINE")
    print(f"  Dataset unificado: {out_unified}")
    print(f"  Listings con alpha_score: {df['alpha_score'].notna().sum()}/{len(df)}")

if __name__ == "__main__":
    main()
