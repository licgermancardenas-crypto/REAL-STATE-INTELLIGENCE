"""
GeoRef API — límites administrativos ARG.
Docs: https://datosgobar.github.io/georef-ar-api/
Sin autenticación. Rate limit: 1000 req/día.

NOTA: GeoRef devuelve centroides para localidades/barrios, NO polígonos.
Para polígonos de barrios CABA → usar gcba.py (BA Data portal).
Para polígonos de comunas CABA → disponibles via municipios (centroide únicamente en free endpoint).
"""
import json
import httpx
from loguru import logger
from config import GEOREF_BASE, DATA_RAW


def get_localidades_caba() -> list[dict]:
    """
    Devuelve las localidades (barrios) de CABA con centroide.
    GeoRef no expone polígonos de barrios — solo centroide lat/lon.
    """
    url = f"{GEOREF_BASE}/localidades"
    params = {
        "provincia": "02",
        "max": 100,
        "campos": "id,nombre,centroide",
    }
    resp = httpx.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    items = data.get("localidades", [])
    logger.info(f"GeoRef: {len(items)} localidades/barrios CABA")
    return items


def get_comunas_caba() -> list[dict]:
    """Devuelve las 15 comunas de CABA (nivel municipio en GeoRef)."""
    url = f"{GEOREF_BASE}/municipios"
    params = {
        "provincia": "02",
        "max": 20,
        "campos": "id,nombre,centroide",
    }
    resp = httpx.get(url, params=params, timeout=30)
    resp.raise_for_status()
    items = resp.json().get("municipios", [])
    logger.info(f"GeoRef: {len(items)} comunas CABA")
    return items


def get_localidades_provincia(provincia_id: str, max: int = 500) -> list[dict]:
    """Localidades de cualquier provincia por ID INDEC (ej: '06' = PBA, '82' = Santa Fe)."""
    url = f"{GEOREF_BASE}/localidades"
    params = {"provincia": provincia_id, "max": max, "campos": "id,nombre,centroide"}
    resp = httpx.get(url, params=params, timeout=60)
    resp.raise_for_status()
    items = resp.json().get("localidades", [])
    logger.info(f"GeoRef: {len(items)} localidades provincia={provincia_id}")
    return items


def get_departamentos_provincia(provincia_id: str) -> list[dict]:
    """Departamentos/partidos de una provincia."""
    url = f"{GEOREF_BASE}/departamentos"
    params = {"provincia": provincia_id, "max": 200, "campos": "id,nombre,centroide"}
    resp = httpx.get(url, params=params, timeout=30)
    resp.raise_for_status()
    items = resp.json().get("departamentos", [])
    logger.info(f"GeoRef: {len(items)} departamentos provincia={provincia_id}")
    return items


def normalizar_direccion(direccion: str, provincia_id: str = "02") -> dict | None:
    """
    Normaliza una dirección y devuelve coordenadas.
    Útil para geocodificar listings sin API paga.
    """
    url = f"{GEOREF_BASE}/direcciones"
    params = {"direccion": direccion, "provincia": provincia_id, "max": 1}
    resp = httpx.get(url, params=params, timeout=30)
    resp.raise_for_status()
    items = resp.json().get("direcciones", [])
    return items[0] if items else None


def save_barrios_caba() -> list[dict]:
    barrios = get_localidades_caba()
    out = DATA_RAW / "georef"
    out.mkdir(exist_ok=True)
    path = out / "barrios_caba.json"
    path.write_text(json.dumps({"localidades": barrios}, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"Guardado → {path} ({len(barrios)} barrios)")
    return barrios


def save_comunas_caba() -> list[dict]:
    comunas = get_comunas_caba()
    out = DATA_RAW / "georef"
    out.mkdir(exist_ok=True)
    path = out / "comunas_caba.json"
    path.write_text(json.dumps({"municipios": comunas}, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"Guardado → {path} ({len(comunas)} comunas)")
    return comunas


if __name__ == "__main__":
    barrios = save_barrios_caba()
    comunas = save_comunas_caba()
    logger.info(f"Listo: {len(barrios)} barrios + {len(comunas)} comunas CABA")

    # Mostrar algunos
    for b in barrios[:5]:
        lat = b["centroide"]["lat"]
        lon = b["centroide"]["lon"]
        logger.info(f"  {b['nombre']:25s} ({lat:.4f}, {lon:.4f})")
