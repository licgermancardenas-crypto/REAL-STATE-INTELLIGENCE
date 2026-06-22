from pydantic import BaseModel
from typing import Any


class AlphaMapResponse(BaseModel):
    type: str
    features: list[dict[str, Any]]


class AlphaScoreRequest(BaseModel):
    lat: float
    lon: float
    city_id: str


class DriverOut(BaseModel):
    name: str
    value: float
    weight: float


class AlphaScoreResponse(BaseModel):
    score: float        # 0-100
    percentile: float   # 0-100 vs ciudad
    drivers: list[DriverOut]
    prediction_24m_pct: float | None
