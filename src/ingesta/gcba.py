"""
GCBA Buenos Aires Data — permisos de obra y catastro.
Portal: https://data.buenosaires.gob.ar/
API CKAN: https://datosabiertos.buenosaires.gob.ar/api/3/action/

Dataset IDs relevantes:
  - Permisos de obra: buscar "permisos-de-obra" en el portal
  - Catastro/parcelas: "parcelas" o "catastro"
  - Usos del suelo: "zonificacion-usos-del-suelo"
"""
import json
import httpx
from loguru import logger
from config import GCBA_BASE, DATA_RAW


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
    results = search_datasets("permisos obra")
    for r in results[:3]:
        logger.info(f"Dataset: {r.get('title')} — id: {r.get('id')}")
