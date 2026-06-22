# Real Estate Intelligence Argentina 🏗️🇦🇷

Sistema de inteligencia geoespacial para análisis de ciudades, barrios y terrenos 
en Argentina, orientado a decisiones de inversión y desarrollo inmobiliario.

Construido 100% con APIs gratuitas, datos públicos y código abierto — sin 
dependencia de herramientas pagas (CoStar, Reonomy, Google Maps, etc).

## Objetivo

Replicar — y en algunos aspectos superar — el nivel de análisis que usan 
fondos institucionales internacionales (Blackstone, Brookfield, PGIM) para 
decidir dónde comprar terrenos y desarrollar real estate, adaptado 100% al 
contexto argentino.

## Filosofía del proyecto

- **Cero costo de infraestructura**: todo corre con APIs gratuitas y datasets públicos.
- **Decisiones basadas en datos, no en intuición**: cada variable del modelo tiene una fuente verificable y un peso explícito.
- **Foco geográfico**: Argentina, empezando por CABA y expandiendo a conurbano y otras provincias.

## Fuentes de datos

| Fuente | Tipo | Variable que aporta |
|---|---|---|
| [GeoRef API](https://apis.datos.gob.ar/georef/api/) | API | Límites administrativos nacionales |
| [Overpass API (OSM)](https://overpass-api.de/) | API | POIs (universidades, hospitales, oficinas) |
| [OpenRouteService](https://openrouteservice.org/) | API (key gratis) | Isócronas de accesibilidad |
| [INDEC Censo 2022](https://www.indec.gob.ar/) | Descarga | Demografía por radio censal — todo el país |
| [GCBA Buenos Aires Data](https://data.buenosaires.gob.ar/) | Descarga/API mixta | Permisos de obra, catastro CABA |
| GTFS Subte/Trenes | Descarga (URL fija) | Red de transporte público AMBA |
| [Google Earth Engine](https://earthengine.google.com/) | API (cuenta gratis, no comercial) | Imágenes satelitales históricas (fase posterior) |
| [Cartografía Censal GBA 2022](https://cartografiacensal-2022.estadistica.ec.gba.gov.ar/index.php/mapoteca/censo-2022/) | Descarga | Radios/fracciones censales Conurbano (24 partidos) |
| [Shapes Estadística PBA](https://mapas.estadistica.ec.gba.gov.ar/portal/apps/sites/#/mapas-estadisticos/pages/descargas-shapes) | Descarga | Shapefiles oficiales PBA por partido/localidad |
| [Estadística EC GBA](https://www.estadistica.ec.gba.gov.ar/) | Descarga/Web | Indicadores socioeconómicos Provincia de Buenos Aires |
| [IGN — Capas SIG](https://www.ign.gob.ar/NuestrasActividades/InformacionGeoespacial/CapasSIG) | WFS/Descarga | Cartografía oficial: provincias, departamentos, localidades, rutas |
| [SimpleMaps ARG](https://simplemaps.com/country/ar/) | Descarga CSV | ~47.000 localidades con lat/lon, población y jerarquía |
| [Poblaciones.org](https://mapa.poblaciones.org/) | Web/API | Población desagregada por radio censal, visualización |

## Roadmap

- [x] Fase 0: Definición de arquitectura y fuentes de datos
- [ ] Fase 1: MVP — pipeline de ingesta validado (GeoRef + Overpass + ORS) sobre un barrio piloto (Palermo, CABA)
- [ ] Fase 2: Carga de límites reales de barrios CABA + datos INDEC por radio censal
- [ ] Fase 3: Modelo de scoring ponderado por zona
- [ ] Fase 4: Imágenes satelitales (Google Earth Engine) — evolución urbana histórica
- [ ] Fase 5: Dashboard interactivo (Streamlit)
- [ ] Fase 6: Expansión a otras ciudades de Argentina

## Stack técnico

- Python 3.11+
- geopandas, pandas, scikit-learn
- PostgreSQL + PostGIS (vía Supabase free tier)
- Streamlit / Folium para visualización

## Estado actual

🚧 En desarrollo — Fase 1 (MVP de ingesta)

## Disclaimer

Proyecto personal de investigación y análisis. No constituye asesoramiento 
de inversión. Los datos provienen de fuentes públicas oficiales y APIs 
gratuitas; verificar siempre con fuentes primarias antes de tomar decisiones 
de inversión reales.

## Autor

German Cardenas
