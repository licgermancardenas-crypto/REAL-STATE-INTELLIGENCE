"""
Construye mapping definitivo: código INDEC (3 dígitos, LINK[2:5]) → nombre partido.

Fuente primaria: Georef API oficial (apis.datos.gob.ar/georef)
Validación cruzada: spatial join con GADM departamentos.gpkg

Resultado: imprime tabla de 31 partidos código ↔ nombre verificado
"""
import json
import sys
import urllib.request
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

ROOT = Path(__file__).parent.parent

import geopandas as gpd
import pandas as pd


def fetch_georef_partidos():
    """Descarga todos los departamentos de PBA desde Georef API."""
    url = "https://apis.datos.gob.ar/georef/api/departamentos?provincia=06&campos=id,nombre&max=200"
    print(f"  GET {url}")
    with urllib.request.urlopen(url, timeout=15) as r:
        data = json.loads(r.read())
    depts = data.get("departamentos", [])
    print(f"  Georef retornó {len(depts)} departamentos de PBA")
    return {d["id"][2:5]: d["nombre"] for d in depts}  # "06028" → "028"


def get_conurbano_codes():
    """Los 31 códigos de depto con >= 50 radios en el bbox."""
    pba = gpd.read_file(ROOT / "data/processed/census/pba_radios.gpkg").to_crs("EPSG:4326")
    cx = pba.geometry.centroid.x.values
    cy = pba.geometry.centroid.y.values
    lon_min, lat_min, lon_max, lat_max = (-59.1, -35.1, -58.2, -34.3)
    mask = (cx >= lon_min) & (cx <= lon_max) & (cy >= lat_min) & (cy <= lat_max)
    c = pba[mask].copy()
    c["cx"] = cx[mask]
    c["cy"] = cy[mask]
    c["depto"] = c["link"].str[2:5]

    agg = c.groupby("depto").agg(
        n=("link", "count"),
        lat=("cy", "mean"),
        lon=("cx", "mean"),
    ).reset_index()
    return agg[agg["n"] >= 50].copy()


def spatial_join_gadm(conurbano_df: pd.DataFrame) -> dict:
    """
    Spatial join con GADM departamentos.gpkg.
    Retorna dict {depto_code: gadm_nombre}.
    """
    gadm = gpd.read_file(ROOT / "data/processed/ign/departamentos.gpkg")
    pba_gadm = gadm[gadm["NAME_1"] == "BuenosAires"].copy()

    centroids = gpd.GeoDataFrame(
        conurbano_df[["depto", "n", "lat", "lon"]].copy(),
        geometry=gpd.points_from_xy(conurbano_df["lon"], conurbano_df["lat"]),
        crs="EPSG:4326",
    )
    joined = gpd.sjoin(centroids, pba_gadm[["nombre", "geometry"]], how="left", predicate="within")
    # fallback nearest
    no_match = joined["nombre"].isna()
    if no_match.any():
        nn = gpd.sjoin_nearest(
            centroids[no_match][["depto", "geometry"]],
            pba_gadm[["nombre", "geometry"]],
            how="left",
        )
        joined.loc[no_match, "nombre"] = nn["nombre"].values
    return dict(zip(joined["depto"], joined["nombre"]))


def main():
    print("=" * 68)
    print("  MAPPING DEFINITIVO: CÓDIGO INDEC → NOMBRE PARTIDO")
    print("=" * 68)

    # 1. Georef API
    print("\n[1] Consultando Georef API ...")
    try:
        georef = fetch_georef_partidos()
    except Exception as e:
        print(f"  ERROR Georef: {e}")
        georef = {}

    # 2. Conurbano codes + centroids
    print("\n[2] Cargando radios del Conurbano ...")
    conurbano = get_conurbano_codes()
    print(f"  {len(conurbano)} partidos con >= 50 radios")

    # 3. GADM spatial join (validación cruzada)
    print("\n[3] Spatial join GADM (validación cruzada) ...")
    gadm_names = spatial_join_gadm(conurbano)

    # 4. Build final mapping
    print("\n[4] Tabla final (Georef primario, GADM como referencia)\n")
    print(f"  {'Código':<6} {'Radios':>6} {'Lat':>8} {'Lon':>8}  {'Nombre Georef':<32}  {'GADM (ref)'}")
    print("  " + "-" * 90)

    mapping = {}
    mismatches = []

    for _, row in conurbano.sort_values("lat", ascending=False).iterrows():
        code  = row["depto"]
        n     = row["n"]
        lat   = row["lat"]
        lon   = row["lon"]
        geo   = georef.get(code, "??NO-EN-GEOREF??")
        gadm  = gadm_names.get(code, "?")

        # Normalizar GADM: strip camelCase
        def clean(s):
            import re
            return re.sub(r"([a-z])([A-Z])", r"\1 \2", s or "")

        gadm_clean = clean(gadm)
        flag = "" if geo != "??NO-EN-GEOREF??" else " <-- VERIFICAR"

        print(f"  {code}    {n:>5}  {lat:>8.3f} {lon:>8.3f}  {geo:<32}  {gadm_clean}{flag}")
        mapping[code] = geo

    # Summary
    print()
    not_found = [c for c, n in mapping.items() if n == "??NO-EN-GEOREF??"]
    if not_found:
        print(f"  ATENCION: {len(not_found)} códigos no en Georef: {not_found}")
        print("  Estos van a necesitar lookup manual o son fuera del GBA 24.")
    else:
        print(f"  Todos los {len(mapping)} partidos identificados via Georef.")

    print("\n# Paste esto en scoring_gba.py / diagnose_gba_pipeline.py:")
    print("CODIGO_PARTIDO = {")
    for code, name in sorted(mapping.items()):
        print(f'    "{code}": "{name}",')
    print("}")

    print("\n" + "=" * 68)


if __name__ == "__main__":
    main()
