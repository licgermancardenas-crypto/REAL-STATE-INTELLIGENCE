"""
OpenRouteService — isócronas de accesibilidad (tiempo a pie / en auto / en bici).
API key gratis en openrouteservice.org (2.000 req/día).
Docs: https://openrouteservice.org/dev/#/api-docs/v2/isochrones
"""
import json
import httpx
from loguru import logger
from config import ORS_BASE, ORS_API_KEY, DATA_RAW

PROFILES = {
    "caminando": "foot-walking",
    "auto": "driving-car",
    "bici": "cycling-regular",
}


def get_isochrone(
    lon: float,
    lat: float,
    minutes: list[int],
    profile: str = "foot-walking",
) -> dict:
    """
    Isócrona desde un punto dado.
    minutes: lista de tiempos en minutos (ej: [5, 10, 15])
    """
    if not ORS_API_KEY:
        raise ValueError("ORS_API_KEY no configurada en .env")

    url = f"{ORS_BASE}/isochrones/{profile}"
    payload = {
        "locations": [[lon, lat]],
        "range": [m * 60 for m in minutes],  # ORS usa segundos
        "range_type": "time",
        "attributes": ["area", "reachfactor"],
    }
    headers = {
        "Authorization": ORS_API_KEY,
        "Content-Type": "application/json",
    }
    resp = httpx.post(url, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()


def get_transit_score(
    lon: float,
    lat: float,
    minutes: int = 10,
) -> float:
    """
    Score de accesibilidad a pie 0-1 basado en área alcanzable en N minutos.
    Normalizado vs área teórica (círculo perfecto sin obstáculos).
    """
    try:
        iso = get_isochrone(lon, lat, [minutes], profile="foot-walking")
        features = iso.get("features", [])
        if not features:
            return 0.0
        area_m2 = features[-1]["properties"].get("area", 0)
        # Área teórica: velocidad media peatonal 5 km/h → radio = 5000/60*minutes metros
        import math
        radio_m = (5000 / 60) * minutes
        area_teorica = math.pi * radio_m ** 2
        score = min(area_m2 / area_teorica, 1.0)
        return round(score, 4)
    except Exception as e:
        logger.warning(f"ORS transit score error ({lon},{lat}): {e}")
        return 0.0


def save_isochrone(nombre: str, lon: float, lat: float, minutes: list[int] = [5, 10, 15]) -> None:
    iso = get_isochrone(lon, lat, minutes)
    out = DATA_RAW / "ors"
    out.mkdir(exist_ok=True)
    path = out / f"isochrone_{nombre}.geojson"
    path.write_text(json.dumps(iso, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"Isócrona guardada → {path}")


if __name__ == "__main__":
    # Piloto: centroide Palermo
    save_isochrone("palermo_centro", lon=-58.4215, lat=-34.5830)
