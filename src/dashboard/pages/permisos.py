"""Vista permisos de obra GCBA — leading indicator de desarrollo."""
import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path

DATA_RAW = Path(__file__).parent.parent.parent.parent / "data" / "raw"


def render(ciudad: str) -> None:
    if ciudad != "CABA":
        st.info("Datos de permisos de obra disponibles solo para CABA (fuente: BA Data).")
        return

    csvs = sorted((DATA_RAW / "gcba").glob("permisos_obra_*.csv")) if (DATA_RAW / "gcba").exists() else []

    if not csvs:
        st.info(
            "Sin datos de permisos. Correr: `python src/ingesta/gcba.py`\n\n"
            "O descargar manualmente desde https://data.buenosaires.gob.ar"
        )
        return

    year = st.selectbox("Año", [p.stem.split("_")[-1] for p in csvs])
    df = pd.read_csv(DATA_RAW / "gcba" / f"permisos_obra_{year}.csv", low_memory=False)

    col1, col2 = st.columns(2)
    col1.metric("Total permisos", f"{len(df):,}")

    if "barrio" in df.columns:
        top_barrios = df["barrio"].value_counts().head(15).reset_index()
        top_barrios.columns = ["Barrio", "Permisos"]
        fig = px.bar(top_barrios, x="Permisos", y="Barrio", orientation="h",
                     title="Top 15 barrios por permisos de obra",
                     color="Permisos", color_continuous_scale="Viridis")
        fig.update_layout(height=500, paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.dataframe(df.head(100))
