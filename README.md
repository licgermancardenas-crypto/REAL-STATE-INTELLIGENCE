# Real State Intelligence

**Location Intelligence Platform — Alpha Generation Engine**

Plataforma de analítica geoespacial que fusiona Big Data urbano con Machine Learning para auditar ciudades a nivel de lote. Identifica zonas con potencial de apreciación inmobiliaria antes de que se vuelvan evidentes para el mercado.

## Stack

| Capa | Tech |
|---|---|
| Frontend | Next.js 15 + MapLibre GL JS + shadcn/ui |
| Backend | FastAPI + Python 3.11 |
| ML | geopandas + PySAL + scikit-learn |
| DB | PostgreSQL + PostGIS |

## Estructura

```
apps/web      → Next.js dashboard
apps/api      → FastAPI REST API
data/etl      → Pipelines de ingesta (OSM, INDEC, Zonaprop)
data/models   → Feature engineering + Alpha Score model
db/migrations → Schema PostGIS
```

## Quick start

```bash
# API
cd apps/api
cp .env.example .env
pip install -r requirements.txt
uvicorn main:app --reload

# Web
cd apps/web
cp .env.local.example .env.local
npm install
npm run dev
```

## Ciudades MVP

- Ciudad de Buenos Aires (CABA)
- Rosario
- Córdoba
- Mendoza
