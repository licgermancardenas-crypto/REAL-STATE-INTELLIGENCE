"""
GeoRef API — límites administrativos ARG.
Docs: https://datosgobar.github.io/georef-ar-api/
Sin autenticación. Rate limit: 1000 req/día.
"""
import json
import httpx
from loguru import logger
from config import GEOREF_BASE, DATA_RAW


def get_barrios_caba() -> list[dict]:
    """Devuelve todos los barrios de CABA con geometría."""
    url = f"{GEOREF_BASE}/asentamientos"
    params = {
        "provincia": "02",  # CABA
        "tipo": "Barrio",
        "max": 100,
        "campos": "id,nombre,geometria",
        "formato": "json",
    }
    resp = httpx.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    barrios = data.get("asentamientos", [])
    logger.info(f"GeoRef: {len(barrios)} barrios CABA")
    return barrios


def get_limite_barrio(nombre: str) -> dict | None:
    """Devuelve el polígono GeoJSON de un barrio específico."""
    url = f"{GEOREF_BASE}/asentamientos"
    params = {"nombre": nombre, "provincia": "02", "max": 1, "campos": "id,nombre,geometria"}
    resp = httpx.get(url, params=params, timeout=30)
    resp.raise_for_status()
    items = resp.json().get("asentamientos", [])
    if not items:
        logger.warning(f"Barrio no encontrado: {nombre}")
        return None
    return items[0]


def get_radios_censales(provincia_id: str = "02") -> dict:
    """Descarga radios censales de una provincia (GeoJSON)."""
    url = f"{GEOREF_BASE}/ubicacion"
    # GeoRef no expone radios directamente — usar INDEC para eso
    # Este endpoint devuelve municipios/localidades
    url = f"{GEOREF_BASE}/municipios"
    params = {"provincia": provincia_id, "max": 500, "campos": "id,nombre,geometria"}
    resp = httpx.get(url, params=params, timeout=60)
    resp.raise_for_status()
    return resp.json()


def save_barrios_caba() -> None:
    barrios = get_barrios_caba()
    out = DATA_RAW / "georef"
    out.mkdir(exist_ok=True)
    (out / "barrios_caba.json").write_text(
        json.dumps({"barrios": barrios}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info(f"Guardado → {out / 'barrios_caba.json'}")


if __name__ == "__main__":
    save_barrios_caba()
    barrio = get_limite_barrio("Palermo")
    if barrio:
        logger.info(f"Palermo geometry type: {barrio.get('geometria', {}).get('type')}")
