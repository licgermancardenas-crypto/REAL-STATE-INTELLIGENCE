"""
Verificación del GeoJSON de GBA:
1. Que nombre_partido exista en todas las features
2. Que los nombres sean correctos (no códigos, no "Desconocido")
3. Muestra 1 radio por partido para confirmar visualmente
"""
import json
from pathlib import Path
from collections import defaultdict

GEOJSON = Path(__file__).parent.parent / "apps/web/public/gba_alpha_scores.geojson"

with open(GEOJSON, encoding="utf-8") as f:
    data = json.load(f)

features = data["features"]
print(f"Total features: {len(features)}")

# Check fields in first feature
props0 = features[0]["properties"]
print(f"\nCampos por feature: {list(props0.keys())}")

# Count by nombre_partido
by_partido = defaultdict(list)
desconocidos = []
sin_campo = 0

for feat in features:
    props = feat["properties"]
    if "nombre_partido" not in props:
        sin_campo += 1
        continue
    nombre = props["nombre_partido"]
    if nombre == "Desconocido":
        desconocidos.append(props.get("link","?"))
    else:
        by_partido[nombre].append(props["alpha_score"])

print(f"\nFeatures sin campo nombre_partido: {sin_campo}")
print(f"Features con 'Desconocido':         {len(desconocidos)}")
if desconocidos:
    print(f"  Links desconocidos (primeros 10): {desconocidos[:10]}")
print(f"Partidos distintos con nombre:      {len(by_partido)}")

print("\n--- Un radio de muestra por partido (link | nombre | score) ---")
seen = set()
for feat in features:
    p = feat["properties"]
    nombre = p.get("nombre_partido","?")
    if nombre not in seen:
        seen.add(nombre)
        code = p.get("depto_code","?")
        score = p.get("alpha_score","?")
        link = p.get("link","?")
        print(f"  código={code}  nombre={nombre:<28}  link={link}  score={score}")

print(f"\n--- Estadísticas por partido (n radios | mediana score) ---")
for nombre, scores in sorted(by_partido.items(), key=lambda x: -len(x[1])):
    n = len(scores)
    med = sorted(scores)[n // 2]
    print(f"  {nombre:<28}  n={n:>5}  mediana={med:.1f}")
