"""
Test fetch: descarga el HTML crudo de Argenprop Palermo y lo guarda
para inspeccionar selectores antes de escribir el scraper real.
Para uso interno — no es el scraper final.
"""
import time, sys
from pathlib import Path
import requests

URL = "https://www.argenprop.com/departamento-en-venta--en-palermo"
OUT = Path(__file__).parent.parent / "data/raw/precios"
OUT.mkdir(parents=True, exist_ok=True)

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
}

print(f"GET {URL} ...")
try:
    resp = requests.get(URL, headers=HEADERS, timeout=20)
    print(f"Status: {resp.status_code}")
    print(f"Content-Type: {resp.headers.get('Content-Type','?')}")
    print(f"Content-Length: {len(resp.content):,} bytes")

    if resp.status_code == 200:
        out_html = OUT / "argenprop_test.html"
        out_html.write_bytes(resp.content)
        print(f"HTML guardado → {out_html}")

        # Quick grep for likely class patterns
        text = resp.text
        print("\n--- Buscando patrones de clases en el HTML ---")
        import re
        # Buscar clases que contengan "card", "listing", "property", "price", "result"
        candidates = re.findall(r'class="([^"]*(?:card|listing|propert|price|result|item|aviso)[^"]*)"', text, re.IGNORECASE)
        unique = sorted(set(candidates))[:30]
        for c in unique:
            print(f"  {c}")

        # Check for CAPTCHA / bot detection markers
        if any(k in text.lower() for k in ["captcha", "cloudflare", "bot detection", "challenge"]):
            print("\nALERTA: Posible detección de bot en el HTML")
        else:
            print("\nSin señales de CAPTCHA/bot-detection en el HTML")

    elif resp.status_code in (403, 429):
        print(f"\nBLOQUEO DETECTADO: {resp.status_code} — parando.")
        sys.exit(1)
    else:
        print(f"\nRespuesta inesperada: {resp.status_code}")
        sys.exit(1)

except requests.exceptions.Timeout:
    print("TIMEOUT — parando.")
    sys.exit(1)
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
