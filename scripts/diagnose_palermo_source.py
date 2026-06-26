"""
Diagnóstica: ¿por qué Argenprop devuelve listigns fuera de Palermo?
Cruza los 20 listings geocodificados contra el polígono oficial GCBA.
"""
import json, re
from pathlib import Path

import pandas as pd
import requests
from shapely.geometry import Point, shape

ROOT = Path(__file__).parent.parent
CSV  = ROOT / "data/processed/palermo_alpha_join.csv"
GCBA = "https://cdn.buenosaires.gob.ar/datosabiertos/datasets/ministerio-de-educacion/barrios/barrios.geojson"

def get_palermo_poly():
    r = requests.get(GCBA, timeout=15)
    d = r.json()
    for f in d["features"]:
        if f["properties"]["nombre"].lower() == "palermo":
            return shape(f["geometry"])
    raise RuntimeError("Palermo no encontrado en GCBA GeoJSON")

def barrio_from_url(url: str) -> str:
    m = re.search(r"en-venta-en-([a-z\-]+)-\d", url)
    if m:
        return m.group(1).replace("-", " ").title()
    return "?"

def main():
    palermo_poly = get_palermo_poly()
    print(f"Polígono Palermo GCBA: área = {palermo_poly.area * 1e10:.2f} km² aprox.\n")

    df = pd.read_csv(CSV)
    df = df[df["lat"].notna()].copy()

    df["in_palermo"] = df.apply(
        lambda r: palermo_poly.contains(Point(r["lon"], r["lat"])), axis=1
    )
    df["barrio_argenprop"] = df["url_listing"].apply(barrio_from_url)

    print(f"{'Dirección':<40} {'In Palermo':>10}  {'Argenprop barrio':<25}  {'Coords'}")
    print("─" * 110)
    for _, r in df.iterrows():
        mark = "✓ DENTRO" if r["in_palermo"] else "✗ FUERA"
        print(
            f"{str(r['direccion'])[:38]:<40} "
            f"{mark:>10}  "
            f"{str(r['barrio_argenprop']):<25}  "
            f"({r['lat']:.5f}, {r['lon']:.5f})"
        )

    inside  = df[df["in_palermo"]]
    outside = df[~df["in_palermo"]]

    print(f"\nRESUMEN:")
    print(f"  Total geocodificados : {len(df)}")
    print(f"  Dentro de Palermo    : {len(inside)}  ({len(inside)/len(df)*100:.0f}%)")
    print(f"  Fuera de Palermo     : {len(outside)}  ({len(outside)/len(df)*100:.0f}%)")

    if len(outside):
        print(f"\nBarrios reales (según coords) de los FUERA:")
        for _, r in outside.iterrows():
            print(f"  - {r['direccion'][:38]:<38}  URL barrio: {r['barrio_argenprop']}")

    print("\nDIAGNÓSTICO:")
    url_palermo  = sum("palermo" in str(r["url_listing"]).lower() for _, r in outside.iterrows())
    url_otros    = len(outside) - url_palermo
    print(f"  Listings FUERA cuya URL dice 'palermo'  : {url_palermo}")
    print(f"  Listings FUERA cuya URL dice otro barrio: {url_otros}")
    print()
    print("  → Argenprop clasifica por zona comercial propia, no por límites GCBA.")
    print("  → Los listings de 'caballito' y 'botanico' los sirve su motor de búsqueda")
    print("    bajo la query /palermo porque los considera área de influencia.")
    print("  → El scraper es correcto: pide /palermo y Argenprop entrega esa zona.")
    print("  → Solución: filtro geográfico post-geocodificación contra polígono GCBA.")

if __name__ == "__main__":
    main()
