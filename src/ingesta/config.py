from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent.parent.parent
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"

DATA_RAW.mkdir(parents=True, exist_ok=True)
DATA_PROCESSED.mkdir(parents=True, exist_ok=True)

# ── APIs ──────────────────────────────────────
GEOREF_BASE = "https://apis.datos.gob.ar/georef/api"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
ORS_BASE = "https://api.openrouteservice.org/v2"
ORS_API_KEY = os.getenv("ORS_API_KEY", "")
GCBA_BASE = "https://datosabiertos.buenosaires.gob.ar/api/3/action"

# ── Supabase ──────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# ── Barrios piloto ────────────────────────────
PILOT_BARRIO = "Palermo"
PILOT_CIUDAD = "Ciudad Autónoma de Buenos Aires"

# ── GTFS ──────────────────────────────────────
GTFS_SUBTE_URL = "https://www.metrovias.com.ar/gtfs/metrovias_gtfs.zip"
GTFS_TRENES_URL = "https://datos.transporte.gob.ar/dataset/gtfs-ferroviario"

# ── Ciudades ──────────────────────────────────
CIUDADES = {
    "caba": {
        "nombre": "Ciudad Autónoma de Buenos Aires",
        "provincia": "Ciudad Autónoma de Buenos Aires",
        "osm_area_id": 3470086,
        "bbox": (-58.5315, -34.7054, -58.3351, -34.5270),
    },
    "rosario": {
        "nombre": "Rosario",
        "provincia": "Santa Fe",
        "osm_area_id": 1288838,
        "bbox": (-60.7611, -33.0202, -60.5802, -32.8700),
    },
    "cordoba": {
        "nombre": "Córdoba",
        "provincia": "Córdoba",
        "osm_area_id": 1262481,
        "bbox": (-64.3069, -31.5009, -64.0673, -31.3179),
    },
    "mendoza": {
        "nombre": "Mendoza",
        "provincia": "Mendoza",
        "osm_area_id": 1288918,
        "bbox": (-68.9631, -32.9901, -68.7689, -32.8239),
    },
}
