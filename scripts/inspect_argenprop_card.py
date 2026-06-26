"""Extrae una card completa para ver todos los campos disponibles."""
import re
from pathlib import Path
from bs4 import BeautifulSoup

html = Path("data/raw/precios/argenprop_test.html").read_text(encoding="utf-8", errors="replace")
soup = BeautifulSoup(html, "html.parser")

cards = soup.find_all("div", class_="card ", limit=3)
if not cards:
    cards = soup.find_all(attrs={"data-item-card": True}, limit=3)

print(f"Cards encontradas: {len(cards)}")

for i, card in enumerate(cards[:2]):
    print(f"\n{'='*60}")
    print(f"CARD {i+1}")
    print(f"{'='*60}")

    # Data attributes (precios, dormitorios, etc.)
    print("\n-- data-attributes --")
    for attr in ["data-item-card", "montonormalizado", "idmoneda", "dormitorios",
                 "ambientes", "idtipopropiedad", "idbarrio", "puntos"]:
        print(f"  {attr}: {card.get(attr, '?')}")

    # Price
    price_el = card.find(class_="card__price")
    currency_el = card.find(class_="card__currency")
    monetary = card.find(class_="card__monetary-values")
    print(f"\n-- precio --")
    print(f"  card__price text: {price_el.get_text(strip=True) if price_el else '?'}")
    print(f"  card__currency:   {currency_el.get_text(strip=True) if currency_el else '?'}")
    print(f"  card__monetary-values: {monetary.get_text(strip=True) if monetary else '?'}")

    # Address
    addr_el = card.find(class_="card__address")
    title_el = card.find(class_="card__title")
    print(f"\n-- dirección/título --")
    print(f"  card__address: {addr_el.get_text(strip=True) if addr_el else '?'}")
    print(f"  card__title:   {title_el.get_text(strip=True) if title_el else '?'}")

    # Features (m², ambientes)
    features_el = card.find(class_="card__main-features")
    print(f"\n-- features --")
    if features_el:
        print(f"  card__main-features: {features_el.get_text(separator='|', strip=True)}")
        for li in features_el.find_all("li"):
            print(f"    li: {li.get_text(strip=True)}")
    else:
        # Try alternative selectors
        for cls in ["card__details-box", "card__info"]:
            el = card.find(class_=cls)
            if el:
                print(f"  {cls}: {el.get_text(separator='|', strip=True)[:200]}")

    # Expenses
    exp_el = card.find(class_="card__expenses")
    print(f"\n-- expensas --")
    print(f"  card__expenses: {exp_el.get_text(strip=True) if exp_el else '?'}")

    # Link
    link_el = card.find("a", href=True)
    print(f"\n-- link --")
    print(f"  href: {link_el['href'] if link_el else '?'}")
