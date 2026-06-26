"""
Genera apps/web/public/value_gap_caba.geojson
Join: data/raw/geo/barrios_gcba.geojson + data/processed/barrio_gap_valor.csv
"""

import json
import csv
import unicodedata
from pathlib import Path

ROOT = Path(__file__).parent.parent

geo_src  = ROOT / "data/raw/geo/barrios_gcba.geojson"
csv_src  = ROOT / "data/processed/barrio_gap_valor.csv"
out_file = ROOT / "apps/web/public/value_gap_caba.geojson"


def normalize(s: str) -> str:
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower().strip()


# Load CSV
gap: dict[str, dict] = {}
with open(csv_src, encoding="utf-8") as f:
    for row in csv.DictReader(f):
        key = normalize(row["barrio"])
        gap[key] = {
            "barrio":      row["barrio"],
            "n":           int(row["n"]),
            "alpha_med":   round(float(row["alpha_med"]), 2),
            "pct_alpha":   int(row["pct_alpha"]),
            "usd_m2_med":  round(float(row["usd_m2_med"]), 1),
            "usd_m2_p25":  round(float(row["usd_m2_p25"]), 1),
            "usd_m2_p75":  round(float(row["usd_m2_p75"]), 1),
            "pct_precio":  int(row["pct_precio"]),
            "precio_norm": round(float(row["precio_norm"]), 2),
            "ratio_gap":   round(float(row["ratio_gap"]), 4),
            "pct_ratio":   int(row["pct_ratio"]),
            "confiable":   int(row["n"]) >= 6,
        }

# Load GeoJSON
with open(geo_src, encoding="utf-8") as f:
    geo = json.load(f)

matched = 0
no_data = 0

for feat in geo["features"]:
    nombre = feat["properties"]["nombre"]
    key    = normalize(nombre)
    if key in gap:
        feat["properties"] = {**feat["properties"], **gap[key]}
        matched += 1
    else:
        feat["properties"]["barrio"]     = nombre
        feat["properties"]["n"]          = 0
        feat["properties"]["confiable"]  = False
        feat["properties"]["ratio_gap"]  = None
        no_data += 1

out_file.parent.mkdir(parents=True, exist_ok=True)
with open(out_file, "w", encoding="utf-8") as f:
    json.dump(geo, f, ensure_ascii=False, separators=(",", ":"))

print(f"OK: {matched} barrios con datos, {no_data} sin datos -> {out_file}")
