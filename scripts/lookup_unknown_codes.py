import json
import urllib.request

with open("apps/web/public/gba_alpha_scores.geojson", encoding="utf-8") as f:
    data = json.load(f)

unknown_codes = set()
for feat in data["features"]:
    if feat["properties"].get("nombre_partido") == "Desconocido":
        unknown_codes.add(feat["properties"]["depto_code"])

print("Codigos desconocidos:", sorted(unknown_codes))
counts = {}
for feat in data["features"]:
    if feat["properties"].get("nombre_partido") == "Desconocido":
        c = feat["properties"]["depto_code"]
        counts[c] = counts.get(c, 0) + 1
print("Radios por codigo desconocido:", counts)

print()
for code in sorted(unknown_codes):
    url = "https://apis.datos.gob.ar/georef/api/departamentos?provincia=06&id=06" + code + "&campos=id,nombre"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            res = json.loads(r.read())
        depts = res.get("departamentos", [])
        if depts:
            nombre = depts[0]["nombre"]
            print(f"  {code} -> {nombre}")
        else:
            print(f"  {code} -> (sin resultado en Georef)")
    except Exception as e:
        print(f"  {code} -> ERROR: {e}")
