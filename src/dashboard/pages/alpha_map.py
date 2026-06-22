"""Alpha Score Map — heatmap por radio censal."""
import streamlit as st
import folium
from streamlit_folium import st_folium
from pathlib import Path
import geopandas as gpd

DATA_PROCESSED = Path(__file__).parent.parent.parent.parent / "data" / "processed"

CIUDAD_CENTER = {
    "CABA": (-34.6037, -58.3816),
    "Rosario": (-32.9442, -60.6505),
    "Córdoba": (-31.4135, -64.1811),
    "Mendoza": (-32.8895, -68.8458),
}

CIUDAD_ID = {
    "CABA": "caba",
    "Rosario": "rosario",
    "Córdoba": "cordoba",
    "Mendoza": "mendoza",
}


def render(ciudad: str) -> None:
    center = CIUDAD_CENTER.get(ciudad, (-34.6037, -58.3816))
    ciudad_id = CIUDAD_ID.get(ciudad, "caba")

    m = folium.Map(location=center, zoom_start=12, tiles="CartoDB dark_matter")

    radios_path = DATA_PROCESSED / "radios" / f"{ciudad_id}_scored.gpkg"
    if radios_path.exists():
        gdf = gpd.read_file(radios_path)
        if "alpha_score" in gdf.columns:
            folium.Choropleth(
                geo_data=gdf.__geo_interface__,
                data=gdf,
                columns=["LINK", "alpha_score"],
                key_on="feature.properties.LINK",
                fill_color="RdYlGn",
                fill_opacity=0.6,
                line_opacity=0.2,
                legend_name="Alpha Score (0-100)",
                nan_fill_color="transparent",
            ).add_to(m)
        else:
            st.warning("Radios sin score. Correr primero el pipeline de scoring.")
    else:
        st.info(
            f"No hay datos procesados para {ciudad}.\n\n"
            "Correr: `python src/ingesta/georef.py` y luego el pipeline de scoring."
        )

    col1, col2, col3 = st.columns(3)
    col1.metric("Zonas analizadas", "—")
    col2.metric("Score promedio", "—")
    col3.metric("Zonas Alpha > 70", "—")

    st_folium(m, width=None, height=600, returned_objects=[])
