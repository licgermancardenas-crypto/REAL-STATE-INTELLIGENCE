"""
Real Estate Intelligence Argentina — Dashboard Streamlit
Fase 5: visualización interactiva de scores y capas de datos.
Correr: streamlit run src/dashboard/app.py
"""
import streamlit as st

st.set_page_config(
    page_title="Real Estate Intelligence AR",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar ───────────────────────────────────
with st.sidebar:
    st.title("🏗️ REI Argentina")
    st.caption("Location Intelligence Platform")
    st.divider()

    ciudad = st.selectbox(
        "Ciudad",
        options=["CABA", "Rosario", "Córdoba", "Mendoza"],
        index=0,
    )

    modo = st.radio(
        "Vista",
        options=["Alpha Score Map", "POIs", "Transporte", "Permisos de Obra"],
        index=0,
    )

    st.divider()
    st.caption("Datos: OSM · GeoRef · INDEC · GCBA · ORS")

# ── Main ──────────────────────────────────────
st.title(f"Real Estate Intelligence — {ciudad}")

if modo == "Alpha Score Map":
    from pages.alpha_map import render
    render(ciudad)
elif modo == "POIs":
    from pages.pois import render
    render(ciudad)
elif modo == "Transporte":
    from pages.transporte import render
    render(ciudad)
elif modo == "Permisos de Obra":
    from pages.permisos import render
    render(ciudad)
