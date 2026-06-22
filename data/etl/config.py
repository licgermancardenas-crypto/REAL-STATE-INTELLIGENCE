from pathlib import Path

ROOT = Path(__file__).parent.parent

RAW_DIR = ROOT / "raw"
PROCESSED_DIR = ROOT / "processed"

RAW_DIR.mkdir(exist_ok=True)
PROCESSED_DIR.mkdir(exist_ok=True)

CITIES = {
    "caba": {
        "name": "Ciudad de Buenos Aires",
        "bbox": (-58.5315, -34.7054, -58.3351, -34.5270),
        "osm_area_id": 3470086,
    },
    "rosario": {
        "name": "Rosario",
        "bbox": (-60.7611, -33.0202, -60.5802, -32.8700),
        "osm_area_id": 1288838,
    },
    "cordoba": {
        "name": "Córdoba",
        "bbox": (-64.3069, -31.5009, -64.0673, -31.3179),
        "osm_area_id": 1262481,
    },
    "mendoza": {
        "name": "Mendoza",
        "bbox": (-68.9631, -32.9901, -68.7689, -32.8239),
        "osm_area_id": 1288918,
    },
}

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Features para el modelo Alpha Score
ALPHA_FEATURES = [
    "poi_density_500m",
    "transit_access_score",
    "street_connectivity",
    "nse_index",
    "price_delta_12m",
    "new_permits_12m",
    "commercial_mix_score",
    "green_space_ratio",
]
