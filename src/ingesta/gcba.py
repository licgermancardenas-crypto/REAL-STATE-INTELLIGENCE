"""
GCBA Buenos Aires Data — barrios, permisos de obra, catastro.
Portal CKAN: https://data.buenosaires.gob.ar/
CDN directo: https://cdn.buenosaires.gob.ar/datosabiertos/datasets/

NOTA subdominio: usar data.buenosaires.gob.ar (no datosabiertos.buenosaires.gob.ar — ese dominio no resuelve).

Datasets CDN directos (no requieren CKAN):
  Barrios:  cdn/.../ministerio-de-educacion/barrios/barrios.geojson
"""
import json
import geopandas as gpd
import httpx
from io import BytesIO
from loguru import logger
from config import GCBA_BASE, GCBA_CDN, DATA_RAW

# URLs CDN fijas — no cambian salvo actualización del portal
_CDN_BARRIOS = f"{GCBA_CDN}/ministerio-de-educacion/barrios/barrios.geojson"


def get_barrios_geojson() -> gpd.GeoDataFrame:
    """
    Descarga el GeoJSON oficial de barrios CABA desde el CDN de BA Data.
    Devuelve GeoDataFrame con polígonos reales (no solo centroides como GeoRef).
    """
    logger.info(f"Descargando barrios CABA: {_CDN_BARRIOS}")
    resp = httpx.get(_CDN_BARRIOS, timeout=60, follow_redirects=True)
    resp.raise_for_status()
    gdf = gpd.read_file(BytesIO(resp.content))
    gdf = gdf.to_crs(epsg=4326)
    logger.info(f"Barrios CABA: {len(gdf)} polígonos | cols: {list(gdf.columns)}")

    out = DATA_RAW / "gcba"
    out.mkdir(exist_ok=True)
    path = out / "barrios_caba.geojson"
    gdf.to_file(path, driver="GeoJSON")
    logger.info(f"Guardado → {path}")
    return gdf


def search_datasets(query: str, rows: int = 10) -> list[dict]:
    url = f"{GCBA_BASE}/package_search"
    resp = httpx.get(url, params={"q": query, "rows": rows}, timeout=30)
    resp.raise_for_status()
    return resp.json().get("result", {}).get("results", [])


def get_dataset_resources(dataset_id: str) -> list[dict]:
    url = f"{GCBA_BASE}/package_show"
    resp = httpx.get(url, params={"id": dataset_id}, timeout=30)
    resp.raise_for_status()
    return resp.json().get("result", {}).get("resources", [])


def download_permisos_obra(year: int = 2024) -> list[dict]:
    """
    Descarga permisos de obra CABA para un año dado.
    Los permisos nuevos son señal leading indicator de desarrollo urbano.
    """
    datasets = search_datasets(f"permisos obra {year}")
    if not datasets:
        logger.warning("Dataset permisos de obra no encontrado")
        return []

    resources = get_dataset_resources(datasets[0]["id"])
    csv_resource = next((r for r in resources if r.get("format", "").upper() == "CSV"), None)
    if not csv_resource:
        logger.warning("No se encontró recurso CSV")
        return []

    url = csv_resource["url"]
    logger.info(f"Descargando permisos de obra: {url}")
    resp = httpx.get(url, timeout=120, follow_redirects=True)
    resp.raise_for_status()

    out = DATA_RAW / "gcba"
    out.mkdir(exist_ok=True)
    path = out / f"permisos_obra_{year}.csv"
    path.write_bytes(resp.content)
    logger.info(f"Guardado → {path} ({len(resp.content) / 1024:.1f} KB)")
    return [{"file": str(path), "rows": resp.text.count("\n")}]


if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "barrios"
    if cmd == "barrios":
        gdf = get_barrios_geojson()
        print(gdf[["BARRIO", "COMUNA", "geometry"]].head() if "BARRIO" in gdf.columns else gdf.head())
    elif cmd == "permisos":
        year = int(sys.argv[2]) if len(sys.argv) > 2 else 2024
        download_permisos_obra(year)
    else:
        results = search_datasets(cmd)
        for r in results[:3]:
            logger.info(f"Dataset: {r.get('title')} — id: {r.get('id')}")
