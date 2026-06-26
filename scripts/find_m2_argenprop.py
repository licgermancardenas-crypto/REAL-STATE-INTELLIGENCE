"""Encuentra dónde están los m² en el HTML de Argenprop."""
import re
from pathlib import Path
from bs4 import BeautifulSoup

html = Path("data/raw/precios/argenprop_test.html").read_text(encoding="utf-8", errors="replace")
soup = BeautifulSoup(html, "html.parser")

# 1. Buscar "m2" o "m²" o "metros" en el HTML
print("=== Ocurrencias de m2/m² en HTML ===")
matches = list(re.finditer(r'(\d+)\s*(?:m²|m2|metros cuadrados?)', html, re.IGNORECASE))
for m in matches[:15]:
    ctx = html[max(0, m.start()-120):m.end()+30].replace("\n"," ").strip()
    print(f"  {m.group()!r}  -->  ...{ctx}...")

# 2. Buscar data-attributes con "sup" (superficie)
print("\n=== Data attributes con 'sup' ===")
for m in re.finditer(r'sup[a-z_]*="([^"]+)"', html, re.IGNORECASE):
    ctx = html[max(0, m.start()-40):m.end()+40].replace("\n"," ")
    print(f"  {m.group()!r}")

# 3. Ver la primera card completa en raw HTML (500 chars después del data-item-card)
print("\n=== Raw card snippet (primera) ===")
m = re.search(r'data-item-card="\d+"', html)
if m:
    # buscar el cierre del primer <div class="card
    card_start = html.rfind('<div', 0, m.start())
    snippet = html[card_start:card_start+1500]
    print(snippet)
