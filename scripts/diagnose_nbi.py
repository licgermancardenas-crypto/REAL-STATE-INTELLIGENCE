"""Diagnose NBI join key and PBA radio structure."""
import geopandas as gpd
import json
import numpy as np
from pathlib import Path

# 1. Check pba_radios columns
pba = gpd.read_file("data/processed/census/pba_radios.gpkg")
print("PBA columns:", list(pba.columns))
print("PBA sample LINK:", pba["link"].head(5).tolist())
print("PBA CRS:", pba.crs)
print()

# 2. CABA radios structure
caba = gpd.read_file("data/processed/census/caba_radios.gpkg")
print("CABA columns:", list(caba.columns))
print("CABA sample LINK:", caba["link"].head(5).tolist())
print("CABA total radios:", len(caba))
print()

# 3. Conurbano filter + partido depto counts
pba_wgs = pba.to_crs("EPSG:4326")
lon_min, lat_min, lon_max, lat_max = -59.1, -35.1, -58.2, -34.3
cx = pba_wgs.geometry.centroid.x
cy = pba_wgs.geometry.centroid.y
mask = (cx >= lon_min) & (cx <= lon_max) & (cy >= lat_min) & (cy <= lat_max)
conurbano = pba_wgs[mask].copy()
conurbano["depto_code"] = conurbano["link"].str[2:5]
print(f"Conurbano radios: {len(conurbano)}")
depto_counts = conurbano.groupby("depto_code").size().sort_values(ascending=False)
print("Depto codes (code: radios):")
for code, cnt in depto_counts.items():
    print(f"  {code}: {cnt} radios")
print()

# 4. Check BA Data NBI file
scratch = Path(r"C:/Users/corra/AppData/Local/Temp/claude/C--Users-corra/2d1665a2-7d70-44cb-ba66-692e880ac07f/scratchpad/caba_radio_geojson.geojson")
if scratch.exists():
    with open(scratch) as f:
        gcba = json.load(f)
    props0 = gcba["features"][0]["properties"]
    print("BA Data fields:", list(props0.keys()))
    print("Sample FRACCION values:", [f["properties"]["FRACCION"] for f in gcba["features"][:5]])
    print("Sample RADIO values:", [f["properties"]["RADIO"] for f in gcba["features"][:5]])
    print("Sample COMUNA values:", [f["properties"]["COMUNA"] for f in gcba["features"][:5]])
    print("Sample CO_FRAC_RA:", [f["properties"]["CO_FRAC_RA"] for f in gcba["features"][:5]])
    print("Total features:", len(gcba["features"]))

    # Check NBI totals
    nbi_con = sum(f["properties"]["H_CON_NBI"] for f in gcba["features"])
    nbi_sin = sum(f["properties"]["H_SIN_NBI"] for f in gcba["features"])
    print(f"H_CON_NBI total: {nbi_con:,}, H_SIN_NBI total: {nbi_sin:,}")
    print(f"NBI rate: {nbi_con/(nbi_con+nbi_sin)*100:.1f}%")
else:
    print("BA Data file NOT found at expected path!")
    # Try alternate paths
    for p in Path(r"C:/Users/corra/AppData/Local/Temp/claude").rglob("*caba*geojson*"):
        print(f"  Found: {p}")
