"""
IGN — Instituto Geográfico Nacional.
WFS oficial: https://wfs.ign.gob.ar/geoserver/ows  (puede estar caído)

FALLBACK: Si IGN WFS no resuelve DNS, se usa GADM 4.1 (UC Davis / CGIAR).
  GADM level 1 = provincias ARG (24 features)
  GADM level 2 = departamentos ARG (~527 features)
  URL: https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_ARG_{level}.json
  Licencia: libre para uso no comercial y académico.

Para localidades (puntos) se usa GeoRef API como fallback (/localidades endpoint).
"""
import json
import httpx
import geopandas as gpd
import pandas as pd
from io import BytesIO
from loguru import logger
from config import IGN_WFS_BASE, IGN_CAPAS, GEOREF_BASE, DATA_RAW, DATA_PROCESSED

# GADM 4.1 — Argentina administrative boundaries
_GADM_BASE = "https://geodata.ucdavis.edu/gadm/gadm4.1/json"
_GADM_LEVELS = {
    "provincias":    ("gadm41_ARG_1.json", "NAME_1"),
    "departamentos": ("gadm41_ARG_2.json", "NAME_2"),
}


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
        params["BBOX"] = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]},EPSG:4326"
    return params


def _fetch_gadm(nombre: str) -> gpd.GeoDataFrame | None:
    """Descarga capa desde GADM 4.1 como fallback cuando IGN WFS no responde."""
    if nombre not in _GADM_LEVELS:
        return None
    filename, name_col = _GADM_LEVELS[nombre]
    url = f"{_GADM_BASE}/{filename}"
    logger.info(f"  Fallback GADM: {url}")
    try:
        resp = httpx.get(url, timeout=180, follow_redirects=True)
        resp.raise_for_status()
        gdf = gpd.read_file(BytesIO(resp.content))
        gdf = gdf.set_crs("EPSG:4326", allow_override=True)
        # Renombrar columna nombre al estándar interno
        if name_col in gdf.columns:
            gdf = gdf.rename(columns={name_col: "nombre"})
        logger.info(f"  GADM OK: {len(gdf)} features")
        return gdf
    except Exception as e:
        logger.warning(f"  GADM falló: {e}")
        return None


def _fetch_localidades_georef(max: int = 5000) -> gpd.GeoDataFrame | None:
    """Fallback para localidades: GeoRef centroides → GeoDataFrame de puntos."""
    try:
        resp = httpx.get(
            f"{GEOREF_BASE}/localidades",
            params={"campos": "id,nombre,centroide,provincia", "max": max},
            timeout=60,
        )
        resp.raise_for_status()
        items = resp.json().get("localidades", [])
        if not items:
            return None
        rows = []
        for item in items:
            c = item.get("centroide", {})
            rows.append({
                "id": item.get("id"),
                "nombre": item.get("nombre"),
                "provincia": item.get("provincia", {}).get("nombre"),
                "lat": c.get("lat"),
                "lon": c.get("lon"),
            })
        df = pd.DataFrame(rows).dropna(subset=["lat", "lon"])
        gdf = gpd.GeoDataFrame(
            df,
            geometry=gpd.points_from_xy(df["lon"], df["lat"]),
            crs="EPSG:4326",
        )
        logger.info(f"  GeoRef localidades OK: {len(gdf)} puntos")
        return gdf
    except Exception as e:
        logger.warning(f"  GeoRef localidades falló: {e}")
        return None


def fetch_layer(
    nombre: str,
    bbox: tuple | None = None,
    max_features: int = 5000,
) -> gpd.GeoDataFrame:
    """
    Descarga una capa IGN. Orden de fallback:
      1. IGN WFS (wfs.ign.gob.ar)
      2. GADM 4.1 para provincias/departamentos
      3. GeoRef centroides para localidades
    """
    layer = IGN_CAPAS.get(nombre)
    if not layer:
        raise ValueError(f"Capa desconocida: {nombre}. Disponibles: {list(IGN_CAPAS)}")

    params = _wfs_params(layer, bbox, max_features)
    logger.info(f"IGN WFS: descargando capa '{nombre}' ({layer}) ...")

    gdf = None
    try:
        resp = httpx.get(IGN_WFS_BASE, params=params, timeout=30)
        resp.raise_for_status()
        gdf = gpd.read_file(BytesIO(resp.content))
        gdf = gdf.set_crs("EPSG:4326", allow_override=True)
        logger.info(f"  IGN WFS OK: {len(gdf)} features")
    except Exception as e:
        logger.warning(f"  IGN WFS falló ({e}). Intentando fallback ...")

    if gdf is None or len(gdf) == 0:
        if nombre == "localidades":
            gdf = _fetch_localidades_georef(max=max_features)
        else:
            gdf = _fetch_gadm(nombre)

    if gdf is None:
        raise RuntimeError(f"No se pudo obtener la capa '{nombre}' desde ninguna fuente.")

    if bbox and "geometry" in gdf.columns:
        from shapely.geometry import box
        aoi = box(*bbox)
        gdf = gdf[gdf.geometry.intersects(aoi)].copy()
        logger.info(f"  Filtrado por bbox: {len(gdf)} features")

    return gdf


def fetch_provincias() -> gpd.GeoDataFrame:
    return fetch_layer("provincias")


def fetch_departamentos(provincia_nombre: str | None = None) -> gpd.GeoDataFrame:
    gdf = fetch_layer("departamentos", max_features=600)
    if provincia_nombre:
        col = next((c for c in gdf.columns if "prov" in c.lower() or c == "NAME_1"), None)
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
    logger.info(f"Guardado → {path} ({len(gdf)} features)")
    return gdf


def save_base_layers() -> None:
    """Descarga capas base nacionales (provincias + departamentos + localidades)."""
    for nombre in ["provincias", "departamentos", "localidades"]:
        save_layer(nombre)


if __name__ == "__main__":
    import sys
    capa = sys.argv[1] if len(sys.argv) > 1 else "provincias"
    save_layer(capa)
