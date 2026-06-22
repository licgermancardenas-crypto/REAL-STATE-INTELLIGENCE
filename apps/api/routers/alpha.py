from fastapi import APIRouter, Query
from models.alpha import AlphaMapResponse, AlphaScoreRequest, AlphaScoreResponse

router = APIRouter()


@router.get("/map/{city_id}", response_model=AlphaMapResponse)
async def get_alpha_map(city_id: str):
    # Returns GeoJSON FeatureCollection con alpha_score por radio censal
    # TODO: query PostGIS → alpha_scores table
    return {"type": "FeatureCollection", "features": []}


@router.post("/score", response_model=AlphaScoreResponse)
async def calculate_score(payload: AlphaScoreRequest):
    # On-demand score para coordenada específica
    # TODO: run inference pipeline
    return {"score": 0.0, "percentile": 0.0, "drivers": []}
