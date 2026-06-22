"""
IGN — Instituto Geográfico Nacional.
WFS oficial: https://wfs.ign.gob.ar/geoserver/ows
Capas SIG: https://www.ign.gob.ar/NuestrasActividades/InformacionGeoespacial/CapasSIG

Sin autenticación. Devuelve GeoJSON via WFS 2.0.
EPSG:4326 pedido explícitamente para compatibilidad directa con PostGIS/Folium.
"""
import json
import httpx
import geopandas as gpd
from io import BytesIO
from loguru import logger
from config import IGN_WFS_BASE, IGN_CAPAS, DATA_RAW, DATA_PROCESSED


def _wfs_params(layer: str, bbox: tuple | None = None, max_features: int = 5000) -> dict:
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeName": layer,
        "outputFormat": "application/json",
        "srsName": "EPSG:4326",
        "count": max_features,
    }
    if bbox:
        # WFS 2.0: BBOX=minx,miny,maxx,maxy,CRS
        params["BBOX"] = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]},EPSG:4326"
    return params


def fetch_layer(
    nombre: str,
    bbox: tuple | None = None,
    max_features: int = 5000,
) -> gpd.GeoDataFrame:
    """
    Descarga una capa IGN via WFS y la devuelve como GeoDataFrame.
    nombre: clave de IGN_CAPAS (ej: 'provincias', 'localidades')
    """
    layer = IGN_CAPAS.get(nombre)
    if not layer:
        raise ValueError(f"Capa desconocida: {nombre}. Disponibles: {list(IGN_CAPAS)}")

    params = _wfs_params(layer, bbox, max_features)
    logger.info(f"IGN WFS: descargando capa '{nombre}' ({layer}) ...")

    resp = httpx.get(IGN_WFS_BASE, params=params, timeout=120)
    resp.raise_for_status()

    gdf = gpd.read_file(BytesIO(resp.content))
    gdf = gdf.set_crs("EPSG:4326", allow_override=True)
    logger.info(f"  {nombre}: {len(gdf)} features")
    return gdf


def fetch_provincias() -> gpd.GeoDataFrame:
    return fetch_layer("provincias")


def fetch_departamentos(provincia_nombre: str | None = None) -> gpd.GeoDataFrame:
    gdf = fetch_layer("departamentos", max_features=600)
    if provincia_nombre:
        col = next((c for c in gdf.columns if "prov" in c.lower()), None)
        if col:
            gdf = gdf[gdf[col].str.contains(provincia_nombre, case=False, na=False)]
    return gdf


def fetch_localidades(bbox: tuple | None = None) -> gpd.GeoDataFrame:
    return fetch_layer("localidades", bbox=bbox, max_features=10000)


def save_layer(nombre: str, bbox: tuple | None = None) -> gpd.GeoDataFrame:
    gdf = fetch_layer(nombre, bbox=bbox)
    out = DATA_PROCESSED / "ign"
    out.mkdir(parents=True, exist_ok=True)
    suffix = f"_{bbox[0]:.2f}" if bbox else ""
    path = out / f"{nombre}{suffix}.gpkg"
    gdf.to_file(path, driver="GPKG")
    logger.info(f"Guardado → {path}")
    return gdf


def save_base_layers() -> None:
    """Descarga capas base nacionales (provincias + departamentos + localidades)."""
    for nombre in ["provincias", "departamentos", "localidades"]:
        save_layer(nombre)


if __name__ == "__main__":
    import sys
    capa = sys.argv[1] if len(sys.argv) > 1 else "provincias"
    save_layer(capa)
