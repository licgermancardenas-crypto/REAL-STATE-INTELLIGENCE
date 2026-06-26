import sys, geopandas as gpd
sys.path.insert(0, 'src')

pba = gpd.read_file('data/processed/census/pba_radios.gpkg').to_crs('EPSG:4326')
cx = pba.geometry.centroid.x.values
cy = pba.geometry.centroid.y.values
lon_min, lat_min, lon_max, lat_max = (-59.1, -35.1, -58.2, -34.3)
mask = (cx >= lon_min) & (cx <= lon_max) & (cy >= lat_min) & (cy <= lat_max)
c = pba[mask].copy()
c['cx'] = cx[mask]
c['cy'] = cy[mask]
c['depto'] = c['link'].str[2:5]

agg = c.groupby('depto').agg(n=('link','count'), lat=('cy','mean'), lon=('cx','mean')).reset_index()
agg = agg[agg['n'] >= 50].sort_values('lat', ascending=False)

# Known partido locations for reference
KNOWN = {
    # Approx lat, lon of main city center
    "Tigre":          (-34.43, -58.58),
    "San Fernando":   (-34.44, -58.56),
    "San Isidro":     (-34.47, -58.52),
    "Vicente Lopez":  (-34.53, -58.49),
    "3 de Febrero":   (-34.60, -58.55),
    "Gral San Marti": (-34.57, -58.53),
    "Hurlingham":     (-34.60, -58.63),
    "Ituzaingo":      (-34.66, -58.67),
    "Moron":          (-34.65, -58.62),
    "Mte Grande(EE)": (-34.82, -58.47),
    "La Matanza":     (-34.77, -58.61),
    "Merlo":          (-34.67, -58.73),
    "Moreno":         (-34.64, -58.79),
    "MalvArg":        (-34.59, -58.70),
    "Jose C Paz":     (-34.52, -58.75),
    "Pilar":          (-34.46, -58.91),
    "Lomas Zamora":   (-34.76, -58.40),
    "Quilmes":        (-34.72, -58.26),
    "Berazategui":    (-34.78, -58.21),
    "Florencio V.":   (-34.83, -58.41),
    "Alm Brown":      (-34.84, -58.39),
    "Esteban Ech.":   (-34.82, -58.47),
    "Avellaneda":     (-34.68, -58.36),
    "Lanus":          (-34.71, -58.40),
}

print("Code   Radios    Lat      Lon    (nearest known lugar)")
print("------------------------------------------------------------")
import math

def closest(lat, lon):
    best, dist = "?", 999
    for name, (klat, klon) in KNOWN.items():
        d = math.sqrt((lat-klat)**2 + (lon-klon)**2)
        if d < dist:
            dist, best = d, name
    return best, dist

for _, r in agg.iterrows():
    lugar, dist = closest(r['lat'], r['lon'])
    print(f"  {r['depto']}   {r['n']:5d}   {r['lat']:.3f}   {r['lon']:.3f}   ~ {lugar} (d={dist:.3f})")
