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

# ── IGN — WFS oficial ─────────────────────────
IGN_WFS_BASE = "https://wfs.ign.gob.ar/geoserver/ows"
IGN_CAPAS = {
    "provincias": "ign:provincias",
    "departamentos": "ign:departamentos",
    "localidades": "ign:localidades",
    "rutas_nac": "ign:rutas",
    "cursos_agua": "ign:hidrografia_linea",
}
IGN_DESCARGA_BASE = "https://www.ign.gob.ar/NuestrasActividades/InformacionGeoespacial/CapasSIG"

# ── Estadística GBA (Dirección Provincial) ────
ESTADISTICA_GBA_BASE = "https://www.estadistica.ec.gba.gov.ar"
ESTADISTICA_GBA_MAPAS = "https://mapas.estadistica.ec.gba.gov.ar"
CARTOGRAFIA_CENSAL_GBA = (
    "https://cartografiacensal-2022.estadistica.ec.gba.gov.ar/index.php/mapoteca/censo-2022/"
)
# Los shapefiles se descargan desde:
SHAPES_GBA_DESCARGA = (
    "https://mapas.estadistica.ec.gba.gov.ar/portal/apps/sites/#/mapas-estadisticos/pages/descargas-shapes"
)

# ── SimpleMaps ARG ────────────────────────────
# CSV de localidades ARG (~47k filas): lat, lng, city, admin_name, population
# Descarga manual (free tier) desde: https://simplemaps.com/country/ar/
SIMPLEMAPS_CSV = DATA_RAW / "simplemaps" / "ar.csv"

# ── Poblaciones.org ───────────────────────────
POBLACIONES_BASE = "https://mapa.poblaciones.org"

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
        "provincia_id_indec": "02",
        "osm_area_id": 3470086,
        "bbox": (-58.5315, -34.7054, -58.3351, -34.5270),
        "fuente_radios": "indec",  # radios: INDEC nacional
    },
    "rosario": {
        "nombre": "Rosario",
        "provincia": "Santa Fe",
        "provincia_id_indec": "82",
        "osm_area_id": 1288838,
        "bbox": (-60.7611, -33.0202, -60.5802, -32.8700),
        "fuente_radios": "indec",
    },
    "cordoba": {
        "nombre": "Córdoba",
        "provincia": "Córdoba",
        "provincia_id_indec": "14",
        "osm_area_id": 1262481,
        "bbox": (-64.3069, -31.5009, -64.0673, -31.3179),
        "fuente_radios": "indec",
    },
    "mendoza": {
        "nombre": "Mendoza",
        "provincia": "Mendoza",
        "provincia_id_indec": "50",
        "osm_area_id": 1288918,
        "bbox": (-68.9631, -32.9901, -68.7689, -32.8239),
        "fuente_radios": "indec",
    },
}

# Partidos del Gran Buenos Aires (24) — radios desde Estadística GBA
PARTIDOS_GBA = [
    "Almirante Brown", "Avellaneda", "Berazategui", "Berisso",
    "Ensenada", "Esteban Echeverría", "Ezeiza", "Florencio Varela",
    "General San Martín", "Hurlingham", "Ituzaingó", "José C. Paz",
    "La Matanza", "Lanús", "Lomas de Zamora", "Malvinas Argentinas",
    "Merlo", "Moreno", "Morón", "Quilmes",
    "San Fernando", "San Isidro", "Tigre", "Tres de Febrero",
    "Vicente López",
]
