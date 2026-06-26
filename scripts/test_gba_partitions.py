import sys
from pathlib import Path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "ingesta"))

from pipeline.gba_full import get_conurbano_deptos

deptos = get_conurbano_deptos(
    ROOT / "data/processed/census/pba_radios.gpkg",
    (-59.1, -35.1, -58.2, -34.3),
    50,
)
print(f"Partidos detectados: {len(deptos)}")
total_radios = sum(v["n_radios"] for v in deptos.values())
print(f"Total radios: {total_radios}")
print()
for code, info in sorted(deptos.items(), key=lambda x: -x[1]["n_radios"]):
    lon_min, lat_min, lon_max, lat_max = info["bbox"]
    print(f"  {code}: {info['n_radios']:4d} radios  bbox({lon_min:.2f},{lat_min:.2f},{lon_max:.2f},{lat_max:.2f})")
