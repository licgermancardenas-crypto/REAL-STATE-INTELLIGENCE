"""
Cross-check GADM para los 7 partidos periféricos (< 50 radios en bbox).
Mismo método que build_partido_mapping.py:
  1. Centroide medio del grupo de radios de cada código
  2. Spatial join within con GADM BuenosAires
  3. Fallback sjoin_nearest si el centroide no cae dentro de ningún polígono GADM
"""
import re
import warnings
warnings.filterwarnings("ignore")

from pathlib import Path
import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).parent.parent

EXTRA_CODES = {
    "119": "Brandsen",
    "126": "Campana",
    "266": "Exaltación de la Cruz",
    "329": "General Las Heras",
    "441": "La Plata",
    "483": "Lobos",
    "497": "Luján",
}

def clean_gadm(s):
    """CamelCase → separated."""
    return re.sub(r"([a-z])([A-Z])", r"\1 \2", s or "?")


def main():
    # 1. Centroides de los 7 códigos en el bbox
    pba = gpd.read_file(ROOT / "data/processed/census/pba_radios.gpkg").to_crs("EPSG:4326")
    cx = pba.geometry.centroid.x.values
    cy = pba.geometry.centroid.y.values
    lon_min, lat_min, lon_max, lat_max = (-59.1, -35.1, -58.2, -34.3)
    mask = (cx >= lon_min) & (cx <= lon_max) & (cy >= lat_min) & (cy <= lat_max)
    c = pba[mask].copy()
    c["cx"] = cx[mask]
    c["cy"] = cy[mask]
    c["depto"] = c["link"].str[2:5]

    subset = c[c["depto"].isin(EXTRA_CODES)].copy()
    agg = subset.groupby("depto").agg(
        n=("link", "count"),
        lat=("cy", "mean"),
        lon=("cx", "mean"),
    ).reset_index()

    centroids_gdf = gpd.GeoDataFrame(
        agg,
        geometry=gpd.points_from_xy(agg["lon"], agg["lat"]),
        crs="EPSG:4326",
    )

    # 2. GADM layer
    gadm = gpd.read_file(ROOT / "data/processed/ign/departamentos.gpkg")
    pba_gadm = gadm[gadm["NAME_1"] == "BuenosAires"].copy()

    # 3. sjoin within
    joined = gpd.sjoin(
        centroids_gdf,
        pba_gadm[["nombre", "geometry"]],
        how="left",
        predicate="within",
    )
    joined = joined[~joined.index.duplicated(keep="first")]

    # 4. Fallback sjoin_nearest for any no-match
    no_match = joined["nombre"].isna()
    if no_match.any():
        nn = gpd.sjoin_nearest(
            centroids_gdf[no_match][["depto", "geometry"]],
            pba_gadm[["nombre", "geometry"]],
            how="left",
        )
        nn = nn[~nn.index.duplicated(keep="first")]
        joined.loc[no_match, "nombre"] = nn["nombre"].values
        joined.loc[no_match, "_fallback"] = True

    if "_fallback" not in joined.columns:
        joined["_fallback"] = False
    else:
        joined["_fallback"] = joined["_fallback"].fillna(False)

    # 5. Build result table
    print("=" * 72)
    print("  CROSS-CHECK GADM — 7 PARTIDOS PERIFÉRICOS")
    print("=" * 72)
    print()
    print(f"  {'Cód':<5} {'n':>4} {'Lat':>8} {'Lon':>8}  {'Georef (fuente)':<28}  {'GADM (cross)':<26}  Match?  Fallback?")
    print("  " + "-" * 92)

    all_ok = True
    issues = []

    for _, row in joined.sort_values("lat", ascending=False).iterrows():
        code    = row["depto"]
        n       = row["n"]
        lat     = row["lat"]
        lon     = row["lon"]
        georef  = EXTRA_CODES[code]
        gadm_r  = clean_gadm(row.get("nombre", "?"))
        fallbk  = bool(row.get("_fallback", False))

        # Compare: strip accents/spaces for fuzzy match
        def norm(s):
            import unicodedata
            s = unicodedata.normalize("NFD", s.lower())
            s = "".join(c for c in s if unicodedata.category(c) != "Mn")
            return s.replace(" ", "").replace(".", "")

        match = norm(georef) == norm(gadm_r)
        flag  = "OK" if match else "DISCREPANCIA"
        if not match:
            all_ok = False
            issues.append((code, georef, gadm_r, fallbk))

        fb_str = "nearest" if fallbk else "within"
        print(f"  {code}   {n:>4}  {lat:>8.3f} {lon:>8.3f}  {georef:<28}  {gadm_r:<26}  {flag:<12}  {fb_str}")

    print()
    if all_ok:
        print("  RESULTADO: Los 7 partidos coinciden en ambas fuentes. Verificacion OK.")
    else:
        print(f"  RESULTADO: {len(issues)} DISCREPANCIA(S) detectada(s):")
        for code, geo, gadm_v, fb in issues:
            print(f"    Código {code}: Georef='{geo}'  GADM='{gadm_v}'  (fallback={fb})")
        print()
        print("  No se modifica nada — reportando al usuario primero.")

    print("=" * 72)


if __name__ == "__main__":
    main()
