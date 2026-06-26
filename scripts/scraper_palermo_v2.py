"""
Scraper Palermo v2 — filtro geográfico en-vuelo contra polígono GCBA.

Cambios respecto a v1:
  - Geocodifica cada listing al instante (Nominatim, 1 req/s)
  - Filtra contra polígono oficial GCBA de Palermo (no zona comercial Argenprop)
  - Cache de geocodificación por dirección (evita re-geocodificar en páginas sucesivas)
  - Para sólo cuando tiene TARGET_PALERMO listings válidos o llega a MAX_PAGES
  - Guarda dos CSV: palermo_v2.csv (dentro) + palermo_v2_rejected.csv (fuera / fallo)
  - Al final corre la correlación usd_m2 ↔ alpha_score

Uso:
  python scripts/scraper_palermo_v2.py
"""
import re, time, random, json, sys
from pathlib import Path

import pandas as pd
import geopandas as gpd
import requests
from bs4 import BeautifulSoup
from shapely.geometry import Point, shape
from scipy import stats as scipy_stats

ROOT = Path(__file__).parent.parent

# ── Config ────────────────────────────────────────────────────────────────────

TARGET_PALERMO = 150
MAX_PAGES      = 25          # ~500 listings brutos máximo
PAGE_DELAY     = (9, 13)     # s — aleatorio entre páginas (evitar detección)
GEO_DELAY      = 1.1         # s — Nominatim policy: max 1 req/s
GEO_VIEWBOX    = "-58.533,-34.521,-58.334,-34.706"   # CABA bbox

# Archivos
GCBA_CACHE   = ROOT / "data/raw/geo/barrios_gcba.geojson"
CSV_OK       = ROOT / "data/raw/precios/palermo_v2.csv"
CSV_REJECTED = ROOT / "data/raw/precios/palermo_v2_rejected.csv"
GEOJSON_ALPHA = ROOT / "apps/web/public/caba_alpha_scores.geojson"

GCBA_URL     = "https://cdn.buenosaires.gob.ar/datosabiertos/datasets/ministerio-de-educacion/barrios/barrios.geojson"
NOMINATIM    = "https://nominatim.openstreetmap.org/search"

AR_BASE  = "https://www.argenprop.com/departamento-en-venta--en-palermo"
AR_HDRS  = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://www.argenprop.com/",
}
NOM_HDRS = {"User-Agent": "RSI-research/1.0 (lic.germancardenas@gmail.com)"}

FIELDNAMES = [
    "id_listing", "direccion", "precio_usd", "m2",
    "dormitorios", "ambientes", "url_listing",
    "lat", "lon", "usd_m2",
]

# ── Palermo polygon ───────────────────────────────────────────────────────────

def load_palermo_polygon():
    GCBA_CACHE.parent.mkdir(parents=True, exist_ok=True)
    if not GCBA_CACHE.exists():
        print("Descargando polígonos GCBA…")
        r = requests.get(GCBA_URL, timeout=20)
        GCBA_CACHE.write_bytes(r.content)
    data = json.loads(GCBA_CACHE.read_text(encoding="utf-8"))
    for f in data["features"]:
        if f["properties"]["nombre"].lower() == "palermo":
            return shape(f["geometry"])
    raise RuntimeError("Palermo no encontrado en GCBA GeoJSON")

# ── Address cleaning ──────────────────────────────────────────────────────────

def clean_address(raw: str) -> str:
    s = re.sub(r",?\s*[Pp]iso\s+\S+", "", raw)
    s = re.sub(r",?\s*\d+[°º][Pp]iso", "", s)
    s = re.sub(r"\s*,\s*$", "", s)
    s = re.sub(r"\s{2,}", " ", s)
    s = re.sub(r"^AV\.?\s+", "Avenida ", s, flags=re.IGNORECASE)
    return s.strip()

# ── Geocoding (with optional fallback without viewbox) ────────────────────────

def geocode(address: str, cache: dict) -> tuple[float, float] | None:
    key = address.lower().strip()
    if key in cache:
        return cache[key]

    for bounded in (1, 0):     # primero con viewbox, luego sin
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
                result = (float(data[0]["lat"]), float(data[0]["lon"]))
                cache[key] = result
                return result
        except Exception as exc:
            print(f"    GEO ERROR: {exc}")
            time.sleep(GEO_DELAY)
            break      # no reintentar en errores de red

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

def parse_page(html: str, page_num: int) -> list[dict]:
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

# ── Spatial join for alpha score ──────────────────────────────────────────────

def assign_alpha(ok_rows: list[dict]) -> pd.DataFrame:
    gdf_radios = gpd.read_file(GEOJSON_ALPHA).set_crs("EPSG:4326", allow_override=True)
    gdf_radios["alpha_score"]   = pd.to_numeric(gdf_radios["alpha_score"],   errors="coerce")
    gdf_radios["alpha_quintil"] = pd.to_numeric(gdf_radios["alpha_quintil"], errors="coerce")

    df = pd.DataFrame(ok_rows)
    gdf_pts = gpd.GeoDataFrame(
        df,
        geometry=[Point(r["lon"], r["lat"]) for r in ok_rows],
        crs="EPSG:4326",
    )
    joined = gpd.sjoin(
        gdf_pts,
        gdf_radios[["link", "alpha_score", "alpha_quintil", "geometry"]],
        how="left", predicate="within",
    )
    joined = joined[~joined.index.duplicated(keep="first")]
    df["radio_link"]    = joined["link"].values
    df["alpha_score"]   = joined["alpha_score"].values
    df["alpha_quintil"] = joined["alpha_quintil"].values
    return df

# ── Correlation report ────────────────────────────────────────────────────────

def print_correlation(df: pd.DataFrame):
    sub = df[df["usd_m2"].notna() & df["alpha_score"].notna()].copy()
    sub["alpha_score"] = pd.to_numeric(sub["alpha_score"], errors="coerce")
    sub = sub[sub["alpha_score"].notna()]
    n   = len(sub)

    W = 80
    print(f"\n{'═'*W}")
    print(f"CORRELACIÓN  usd_m2 ↔ alpha_score  (n={n} listings con m² conocido)")
    print(f"{'═'*W}")

    if n < 5:
        print(f"  Insuficientes datos (n={n}). Necesitás ≥5 con m² conocido.")
        return

    r_p, p_val = scipy_stats.pearsonr(sub["usd_m2"], sub["alpha_score"])
    r_s, _     = scipy_stats.spearmanr(sub["usd_m2"], sub["alpha_score"])

    print(f"  Pearson  r = {r_p:+.3f}  (p={p_val:.3f})")
    print(f"  Spearman ρ = {r_s:+.3f}")
    print()

    if p_val < 0.05:
        direction = "positiva" if r_p > 0 else "negativa"
        strength  = "fuerte" if abs(r_p) >= 0.5 else "moderada"
        print(f"  → Correlación {direction} {strength} SIGNIFICATIVA (p<0.05).")
        if r_p > 0:
            print("    Zonas con mayor Alpha Score tienden a mayor precio/m². Hipótesis confirmada.")
        else:
            print("    Zonas con mayor Alpha Score tienden a MENOR precio/m². Efecto inesperado.")
    elif abs(r_p) >= 0.25:
        print(f"  → Tendencia {'positiva' if r_p > 0 else 'negativa'} pero no significativa (p={p_val:.2f}).")
        print(f"    Señal débil, aumentá la muestra.")
    else:
        print(f"  → Sin correlación clara (r≈0, p={p_val:.2f}).")
        print(f"    Posibles causas: varianza en calidad/estado de inmuebles, outliers.")

    # Mediana por quintil
    df2 = sub.copy()
    df2["q"] = pd.to_numeric(df2["alpha_quintil"], errors="coerce")
    print(f"\n  Mediana usd/m² por quintil Alpha Score (Palermo real):")
    print(f"  {'Q':>2}  {'Mediana USD/m²':>15}  {'n':>4}")
    for q in sorted(df2["q"].dropna().unique()):
        seg = df2[df2["q"] == q]
        print(f"  Q{int(q):>1}  {seg['usd_m2'].median():>15,.0f}  {len(seg):>4}")

    # Top 10 por usd_m2
    print(f"\n  Top 10 listings por USD/m²:")
    top = sub.nlargest(10, "usd_m2")[
        ["direccion", "precio_usd", "m2", "usd_m2", "alpha_score", "alpha_quintil"]
    ]
    print(f"  {'Dirección':<35} {'USD':>9} {'m²':>5} {'$/m²':>7} {'Score':>6} Q")
    print(f"  {'─'*35} {'─'*9} {'─'*5} {'─'*7} {'─'*6} ─")
    for _, r in top.iterrows():
        print(
            f"  {str(r['direccion'])[:34]:<35} "
            f"{int(r['precio_usd']):>9,} "
            f"{int(r['m2']):>5} "
            f"{int(r['usd_m2']):>7,} "
            f"{r['alpha_score']:>6.1f} "
            f"Q{int(r['alpha_quintil'])}"
        )

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    palermo_poly  = load_palermo_polygon()
    geo_cache     = {}
    seen_ids      = set()
    ok_rows       = []
    rejected_rows = []
    session       = requests.Session()
    session.headers.update(AR_HDRS)

    print(f"Target: {TARGET_PALERMO} listings dentro del Palermo GCBA\n")

    for page_num in range(1, MAX_PAGES + 1):

        if len(ok_rows) >= TARGET_PALERMO:
            print(f"\nTarget alcanzado ({len(ok_rows)} listings). Fin del scraping.")
            break

        # ── Fetch page ────────────────────────────────────────────────────
        if page_num > 1:
            delay = random.uniform(*PAGE_DELAY)
            print(f"\nEsperando {delay:.1f}s antes de página {page_num}…")
            time.sleep(delay)

        url = AR_BASE if page_num == 1 else f"{AR_BASE}--pagina-{page_num}"
        print(f"GET página {page_num}: {url}")

        try:
            resp = session.get(url, timeout=20)
        except requests.exceptions.Timeout:
            print("TIMEOUT — abortando.")
            break
        except requests.exceptions.ConnectionError as e:
            print(f"CONNECTION ERROR: {e} — abortando.")
            break

        print(f"  HTTP {resp.status_code} | {len(resp.content):,} bytes")
        if resp.status_code in (403, 429):
            print(f"BLOQUEO ({resp.status_code}) — parando sin reintentar.")
            break
        if resp.status_code != 200:
            print(f"Status inesperado {resp.status_code} — abortando.")
            break

        cards = parse_page(resp.text, page_num)
        if not cards:
            print("  Sin listings en esta página — fin de resultados.")
            break

        new_this_page = 0
        # ── Geocode + filter ──────────────────────────────────────────────
        for row in cards:
            lid = row["id_listing"]
            if lid in seen_ids:
                continue
            seen_ids.add(lid)

            raw_addr = str(row["direccion"]).strip()
            if not raw_addr:
                rejected_rows.append({**row, "geo_status": "no_address", "in_palermo": False})
                continue

            addr_clean = clean_address(raw_addr)
            coords = geocode(addr_clean, geo_cache)

            if coords is None:
                print(f"  GEO FAIL: {raw_addr[:50]}")
                rejected_rows.append({**row, "geo_status": "geo_fail", "in_palermo": False})
                continue

            lat, lon = coords
            pt = Point(lon, lat)
            in_palermo = palermo_poly.contains(pt)

            if in_palermo:
                usd_m2 = round(row["precio_usd"] / row["m2"]) if row["m2"] else None
                ok_rows.append({**row, "lat": lat, "lon": lon, "usd_m2": usd_m2})
                new_this_page += 1
                print(
                    f"  ✓ [{len(ok_rows):>3}] {raw_addr[:45]:<45}"
                    f" → ({lat:.5f},{lon:.5f})"
                )
            else:
                rejected_rows.append({
                    **row, "lat": lat, "lon": lon,
                    "geo_status": "ok", "in_palermo": False,
                })
                print(f"  ✗ FUERA  {raw_addr[:45]:<45} → ({lat:.5f},{lon:.5f})")

        print(
            f"  Página {page_num}: +{new_this_page} Palermo | "
            f"total OK={len(ok_rows)} | rechazados={len(rejected_rows)}"
        )

    # ── Save CSVs ─────────────────────────────────────────────────────────
    CSV_OK.parent.mkdir(parents=True, exist_ok=True)

    if ok_rows:
        pd.DataFrame(ok_rows).to_csv(CSV_OK, index=False, encoding="utf-8")
        print(f"\nGuardado: {CSV_OK}  ({len(ok_rows)} listings)")

    if rejected_rows:
        pd.DataFrame(rejected_rows).to_csv(CSV_REJECTED, index=False, encoding="utf-8")
        print(f"Guardado: {CSV_REJECTED}  ({len(rejected_rows)} rechazados)")

    if not ok_rows:
        print("Sin datos válidos. Fin.")
        sys.exit(1)

    # ── Spatial join alpha score + correlación ────────────────────────────
    print(f"\nAsignando Alpha Score a {len(ok_rows)} listings…")
    df = assign_alpha(ok_rows)

    print(f"\n{'═'*80}")
    print(f"TABLA: {len(df)} listings Palermo real × Alpha Score")
    print(f"{'═'*80}")
    df_show = df[df["usd_m2"].notna()].copy()
    df_show["alpha_str"] = df_show["alpha_score"].apply(
        lambda x: f"{x:.1f}" if pd.notna(x) else "—"
    )
    print(
        f"{'Dirección':<40} {'USD':>9} {'m²':>5} {'$/m²':>7} {'Score':>6} Q"
    )
    print("─" * 75)
    for _, r in df_show.sort_values("alpha_score", ascending=False).head(30).iterrows():
        print(
            f"{str(r['direccion'])[:39]:<40}"
            f"{int(r['precio_usd']):>9,}"
            f"{int(r['m2']):>5}"
            f"{int(r['usd_m2']):>7,}"
            f"{r['alpha_str']:>7}"
            f" Q{str(r.get('alpha_quintil','?'))[:1]}"
        )
    if len(df_show) > 30:
        print(f"  … y {len(df_show)-30} más (ver CSV)")

    print_correlation(df)

    # Estadísticas de filtrado
    total_scraped = len(ok_rows) + len(rejected_rows)
    print(f"\n{'═'*80}")
    print(f"ESTADÍSTICAS DE FILTRADO")
    print(f"{'─'*80}")
    print(f"  Listings scrapeados (brutos únicos)  : {total_scraped}")
    print(f"  Dentro del polígono Palermo GCBA     : {len(ok_rows)}  ({len(ok_rows)/total_scraped*100:.0f}%)")
    print(f"  Fuera / geocoding fallido            : {len(rejected_rows)}  ({len(rejected_rows)/total_scraped*100:.0f}%)")
    rejection_reasons = {}
    for r in rejected_rows:
        k = r.get("geo_status", "?")
        rejection_reasons[k] = rejection_reasons.get(k, 0) + 1
    for k, v in rejection_reasons.items():
        print(f"    {k}: {v}")

if __name__ == "__main__":
    main()
