"""Vista POIs OSM por categoría."""
import json
import streamlit as st
import folium
from streamlit_folium import st_folium
from pathlib import Path

DATA_RAW = Path(__file__).parent.parent.parent.parent / "data" / "raw"

POI_COLORS = {
    "educacion": "blue",
    "salud": "red",
    "transporte": "green",
    "comercio": "orange",
    "oficinas": "purple",
    "espacios_verdes": "darkgreen",
}

CIUDAD_CENTER = {
    "CABA": (-34.6037, -58.3816),
    "Rosario": (-32.9442, -60.6505),
    "Córdoba": (-31.4135, -64.1811),
    "Mendoza": (-32.8895, -68.8458),
}


def render(ciudad: str) -> None:
    center = CIUDAD_CENTER.get(ciudad, (-34.6037, -58.3816))
    ciudad_id = {"CABA": "caba", "Rosario": "rosario", "Córdoba": "cordoba", "Mendoza": "mendoza"}[ciudad]
    osm_dir = DATA_RAW / "osm" / ciudad_id

    categorias = st.multiselect(
        "Categorías",
        options=list(POI_COLORS.keys()),
        default=["transporte", "educacion"],
    )

    m = folium.Map(location=center, zoom_start=13, tiles="CartoDB positron")

    total = 0
    for cat in categorias:
        path = osm_dir / f"{cat}.json"
        if not path.exists():
            continue
        elements = json.loads(path.read_text())["elements"]
        for el in elements:
            lat = el.get("lat") or el.get("center", {}).get("lat")
            lon = el.get("lon") or el.get("center", {}).get("lon")
            if lat and lon:
                folium.CircleMarker(
                    location=[lat, lon],
                    radius=4,
                    color=POI_COLORS.get(cat, "gray"),
                    fill=True,
                    fill_opacity=0.7,
                    tooltip=f"{cat}: {el.get('tags', {}).get('name', '')}",
                ).add_to(m)
                total += 1

    st.caption(f"{total} POIs en mapa")
    st_folium(m, width=None, height=600, returned_objects=[])
