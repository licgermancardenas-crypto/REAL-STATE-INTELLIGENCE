import re
from pathlib import Path

html = Path("data/raw/precios/argenprop_test.html").read_text(encoding="utf-8", errors="replace")

# 1. What triggered bot-detection alert?
print("=== Bot-detection context ===")
for m in re.finditer(r"captcha|cloudflare|bot.detection|challenge", html, re.IGNORECASE):
    ctx = html[max(0, m.start()-80):m.start()+100].replace("\n", " ")
    print(f"  pos={m.start()}: ...{ctx.strip()}...")

# 2. Are USD prices present in the raw HTML?
prices = re.findall(r"USD[\s\xa0]\d[\d\.]+", html)
print(f"\n=== Precios USD en HTML: {len(prices)} ===")
for p in prices[:10]:
    print(f"  {p}")

# 3. card__address content
addrs = re.findall(r'card__address[^>]*>([^<]{3,80})<', html)
print(f"\n=== card__address ({len(addrs)} encontradas) ===")
for a in addrs[:5]:
    print(f"  {a.strip()}")

# 4. All card__ classes
card_classes = sorted(set(re.findall(r'class="([^"]*card__[^"]*)"', html)))
print(f"\n=== Clases card__ ({len(card_classes)}) ===")
for c in card_classes[:30]:
    print(f"  {c}")

# 5. Look for listing count
listing_counts = re.findall(r'\d+\s*(?:resultados|propiedades|avisos|publicaciones)', html, re.IGNORECASE)
print(f"\n=== Conteo de listings ===")
for lc in listing_counts[:5]:
    print(f"  {lc}")

# 6. Show a 2KB snippet around the first "card " class to see full structure
m = re.search(r'class="card\s', html)
if m:
    snippet = html[m.start():m.start()+2000]
    print(f"\n=== Snippet primer card (2KB) ===")
    print(snippet[:2000])
