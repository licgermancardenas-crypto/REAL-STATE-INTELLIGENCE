import geopandas as gpd

gdf = gpd.read_file('data/processed/ign/departamentos.gpkg')

pba = gdf[gdf['NAME_1'] == 'BuenosAires'].copy()
print(f'PBA records: {len(pba)}')
print()
print('CC_2 sample:', pba['CC_2'].head(10).tolist())
print('GID_2 sample:', pba['GID_2'].head(10).tolist())
print()
for _, row in pba.sort_values('nombre').iterrows():
    print(f"  CC_2={str(row['CC_2']).strip():>6}  GID_2={row['GID_2']}  nombre={row['nombre']}")
