"""Vista red de transporte público (GTFS)."""
import streamlit as st
import folium
from streamlit_folium import st_folium
import geopandas as gpd
from pathlib import Path

DATA_PROCESSED = Path(__file__).parent.parent.parent.parent / "data" / "processed"

CIUDAD_CENTER = {
    "CABA": (-34.6037, -58.3816),
    "Rosario": (-32.9442, -60.6505),
    "Córdoba": (-31.4135, -64.1811),
    "Mendoza": (-32.8895, -68.8458),
}


def render(ciudad: str) -> None:
    center = CIUDAD_CENTER.get(ciudad, (-34.6037, -58.3816))
    m = folium.Map(location=center, zoom_start=12, tiles="CartoDB dark_matter")

    stops_path = DATA_PROCESSED / "transport" / "subte_stops.gpkg"
    if stops_path.exists():
        stops = gpd.read_file(stops_path)
        for _, row in stops.iterrows():
            if row.geometry:
                folium.CircleMarker(
                    location=[row.geometry.y, row.geometry.x],
                    radius=5,
                    color="#00ff88",
                    fill=True,
                    fill_opacity=0.8,
                    tooltip=row.get("stop_name", "Parada"),
                ).add_to(m)
        st.caption(f"{len(stops)} paradas de subte")
    else:
        st.info("Datos GTFS no disponibles. Correr: `python src/ingesta/gtfs.py`")

    st_folium(m, width=None, height=600, returned_objects=[])
