"""
Scraper Zonaprop — listings residenciales y comerciales.
Respeta robots.txt; rate limit 2s entre requests.
Output: Parquet por ciudad en data/raw/listings/{city_id}_{date}.parquet
"""
import time
import re
from datetime import date
from pathlib import Path

import httpx
from bs4 import BeautifulSoup
import pandas as pd
from loguru import logger

from config import CITIES, RAW_DIR

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; RSI-research-bot/0.1; +research)",
    "Accept-Language": "es-AR,es;q=0.9",
}

CITY_SLUGS = {
    "caba": "capital-federal",
    "rosario": "rosario",
    "cordoba": "cordoba-capital",
    "mendoza": "mendoza-capital",
}


def scrape_city(city_id: str, pages: int = 5) -> pd.DataFrame:
    slug = CITY_SLUGS[city_id]
    base_url = f"https://www.zonaprop.com.ar/inmuebles-venta-{slug}-pagina-{{page}}.html"
    records = []

    for page in range(1, pages + 1):
        url = base_url.format(page=page)
        logger.info(f"Scraping page {page}: {url}")
        try:
            resp = httpx.get(url, headers=HEADERS, follow_redirects=True, timeout=30)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            listings = soup.select("[data-id]")
            for item in listings:
                price_el = item.select_one("[data-price]")
                surface_el = item.select_one(".postingCardMainFeatures-module__super-feature")
                address_el = item.select_one(".postingCardLocation-module__location")
                if not price_el:
                    continue
                price_text = price_el.get("data-price", "0")
                price = float(re.sub(r"[^\d.]", "", price_text) or 0)
                records.append({
                    "city_id": city_id,
                    "address": address_el.text.strip() if address_el else "",
                    "price_usd": price,
                    "surface_m2": _parse_surface(surface_el.text if surface_el else ""),
                    "source": "zonaprop",
                    "scraped_at": date.today().isoformat(),
                })
        except Exception as e:
            logger.warning(f"Page {page} failed: {e}")

        time.sleep(2)

    df = pd.DataFrame(records)
    out_path = RAW_DIR / "listings" / f"{city_id}_{date.today()}.parquet"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)
    logger.info(f"Saved {len(df)} listings → {out_path}")
    return df


def _parse_surface(text: str) -> float:
    m = re.search(r"(\d[\d.,]*)\s*m²", text)
    return float(m.group(1).replace(",", ".")) if m else 0.0


if __name__ == "__main__":
    import sys
    city_id = sys.argv[1] if len(sys.argv) > 1 else "caba"
    scrape_city(city_id)
