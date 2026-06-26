"""Revisa card__main-features de todas las cards para ver si hay m² estructurado."""
import re
from pathlib import Path
from bs4 import BeautifulSoup

html = Path("data/raw/precios/argenprop_test.html").read_text(encoding="utf-8", errors="replace")
soup = BeautifulSoup(html, "html.parser")

# Usar selector correcto: la card es el <a> con data-item-card
cards = soup.find_all("a", attrs={"data-item-card": True})
print(f"Cards (anchor) encontradas: {len(cards)}")

for i, card in enumerate(cards[:20]):
    precio = card.get("montonormalizado", "?")
    moneda = card.get("idmoneda", "?")
    dorms  = card.get("dormitorios", "?")
    title  = card.find(class_="card__title")
    title_text = title.get_text(strip=True) if title else ""

    features = card.find(class_="card__main-features")
    feat_items = []
    if features:
        feat_items = [li.get_text(strip=True) for li in features.find_all("li")]

    # Buscar m² en features
    m2_feat = [x for x in feat_items if re.search(r'\d+\s*m', x, re.IGNORECASE)]
    # Buscar m² en título
    m2_title = re.search(r'(\d+[\.,]?\d*)\s*m[²2]?(?:\s|$|,|\+)', title_text, re.IGNORECASE)

    m2_val = ""
    if m2_feat:
        m2_val = f"feat:{m2_feat[0]}"
    elif m2_title:
        m2_val = f"title:{m2_title.group().strip()}"

    addr = card.find(class_="card__address")
    addr_text = addr.get_text(strip=True) if addr else ""

    print(f"  [{i+1:02d}] USD{precio} | dorms={dorms} | m2={m2_val or 'NO'} | {addr_text[:30]} | feats={feat_items}")
