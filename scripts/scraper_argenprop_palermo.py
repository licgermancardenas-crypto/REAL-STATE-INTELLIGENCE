"""
Scraper lento y seguro de Argenprop — Departamentos en venta en Palermo.
Politicas:
  - 8-10s delay entre pages (random para no parecer bot)
  - Máximo 3 páginas (~60 listings)
  - Para inmediatamente ante 403/429/timeout
  - No reintenta en caso de bloqueo
"""
import re
import sys
import time
import random
import csv
from pathlib import Path

import requests
from bs4 import BeautifulSoup

OUT_DIR = Path(__file__).parent.parent / "data/raw/precios"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_CSV = OUT_DIR / "palermo_sample.csv"

BASE_URL = "https://www.argenprop.com/departamento-en-venta--en-palermo"
PAGE_URLS = [
    BASE_URL,
    BASE_URL + "?pagina-2",
    BASE_URL + "?pagina-3",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Referer": "https://www.argenprop.com/",
}

FIELDNAMES = [
    "id_listing", "barrio", "ciudad", "tipo",
    "precio_usd", "m2_cubiertos", "dormitorios", "ambientes",
    "direccion", "url_listing",
]


def extract_m2(feat_items: list[str]) -> float | None:
    for item in feat_items:
        m = re.search(r"(\d+[\.,]?\d*)\s*m", item, re.IGNORECASE)
        if m:
            val_str = m.group(1).replace(",", ".")
            try:
                return float(val_str)
            except ValueError:
                pass
    return None


def extract_ambientes(feat_items: list[str], card_title: str) -> str:
    for item in feat_items:
        if "ambiente" in item.lower():
            return item.strip()
        if "monoam" in item.lower():
            return "Monoambiente"
    # fallback: buscar en título
    m = re.search(r"(\d)\s*ambiente|monoambiente", card_title, re.IGNORECASE)
    if m:
        return m.group(0).strip()
    return ""


def parse_page(html: str, page_num: int) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.find_all("a", attrs={"data-item-card": True})
    print(f"  [{page_num}] cards encontradas: {len(cards)}")

    rows = []
    for card in cards:
        id_listing = card.get("data-item-card", "")
        id_moneda  = card.get("idmoneda", "")
        monto_raw  = card.get("montonormalizado", "")

        # Solo USD (idmoneda=2)
        if id_moneda != "2":
            continue
        try:
            precio_usd = int(monto_raw)
        except (ValueError, TypeError):
            continue
        if precio_usd <= 0:
            continue

        # Features
        features_el = card.find(class_="card__main-features")
        feat_items = []
        if features_el:
            feat_items = [li.get_text(strip=True) for li in features_el.find_all("li")]

        title_el    = card.find(class_="card__title")
        title_text  = title_el.get_text(strip=True) if title_el else ""

        m2          = extract_m2(feat_items)
        dormitorios = card.get("dormitorios", "").strip()
        ambientes   = extract_ambientes(feat_items, title_text)

        addr_el     = card.find(class_="card__address")
        direccion   = addr_el.get_text(strip=True) if addr_el else ""

        href = card.get("href", "")
        url_listing = f"https://www.argenprop.com{href}" if href.startswith("/") else href

        rows.append({
            "id_listing":   id_listing,
            "barrio":       "Palermo",
            "ciudad":       "CABA",
            "tipo":         "Departamento",
            "precio_usd":   precio_usd,
            "m2_cubiertos": m2 if m2 is not None else "",
            "dormitorios":  dormitorios,
            "ambientes":    ambientes,
            "direccion":    direccion,
            "url_listing":  url_listing,
        })

    return rows


def main():
    all_rows: list[dict] = []
    session = requests.Session()
    session.headers.update(HEADERS)

    for i, url in enumerate(PAGE_URLS, start=1):
        delay = random.uniform(8, 10)
        if i > 1:
            print(f"  Esperando {delay:.1f}s antes de page {i}...")
            time.sleep(delay)

        print(f"GET page {i}: {url}")
        try:
            resp = session.get(url, timeout=20)
        except requests.exceptions.Timeout:
            print("TIMEOUT — parando.")
            break
        except requests.exceptions.ConnectionError as e:
            print(f"CONNECTION ERROR: {e} — parando.")
            break

        print(f"  Status: {resp.status_code} | Size: {len(resp.content):,} bytes")

        if resp.status_code in (403, 429):
            print(f"BLOQUEO DETECTADO ({resp.status_code}) — parando sin reintentar.")
            break
        if resp.status_code != 200:
            print(f"Status inesperado {resp.status_code} — parando.")
            break

        rows = parse_page(resp.text, i)
        all_rows.extend(rows)
        print(f"  Total acumulado: {len(all_rows)} listings")

    if not all_rows:
        print("Sin datos — no se escribe CSV.")
        sys.exit(1)

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\nGuardado: {OUT_CSV} ({len(all_rows)} filas)")

    # Stats
    usd_prices = [r["precio_usd"] for r in all_rows]
    m2_vals    = [float(r["m2_cubiertos"]) for r in all_rows if r["m2_cubiertos"]]
    precio_m2  = [r["precio_usd"] / float(r["m2_cubiertos"])
                  for r in all_rows if r["m2_cubiertos"]]

    print(f"\n--- Resumen ---")
    print(f"  Listings:       {len(all_rows)}")
    print(f"  Con m²:         {len(m2_vals)}/{len(all_rows)}")
    print(f"  Precio USD min: {min(usd_prices):,.0f}")
    print(f"  Precio USD max: {max(usd_prices):,.0f}")
    print(f"  Precio USD avg: {sum(usd_prices)/len(usd_prices):,.0f}")
    if precio_m2:
        print(f"  USD/m² avg:     {sum(precio_m2)/len(precio_m2):,.0f}")
        print(f"  USD/m² median:  {sorted(precio_m2)[len(precio_m2)//2]:,.0f}")

    # Muestra de 10 filas
    print(f"\n--- Muestra (10 filas) ---")
    header = f"{'Dirección':<35} {'USD':>10} {'m²':>6} {'dorms':>5} {'ambientes':<15}"
    print(header)
    print("-" * len(header))
    for r in all_rows[:10]:
        print(
            f"{r['direccion'][:34]:<35} "
            f"{r['precio_usd']:>10,} "
            f"{str(r['m2_cubiertos']):>6} "
            f"{r['dormitorios']:>5} "
            f"{r['ambientes']:<15}"
        )


if __name__ == "__main__":
    main()
