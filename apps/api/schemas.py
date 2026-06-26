from typing import Any, Optional
from pydantic import BaseModel


class RadioScore(BaseModel):
    link: str
    alpha_score: float
    alpha_quintil: int
    score_version: str
    tot_pob: Optional[float] = None
    densidad_pob: Optional[float] = None
    poi_total_count: Optional[int] = None
    poi_total_density: Optional[float] = None
    div_entropy_ex_transporte: Optional[float] = None
    dist_subte_m: Optional[float] = None
    nearest_subte: Optional[str] = None
    pct_sin_nbi: Optional[float] = None


class GBARadioScore(BaseModel):
    link: str
    alpha_score: float
    alpha_quintil: int
    score_tipo: str
    nombre_partido: Optional[str] = None
    densidad_pob: Optional[float] = None
    tot_pob: Optional[float] = None


class CityStats(BaseModel):
    city: str
    count: int
    mean: float
    median: float
    p25: float
    p75: float
    max: float
    premium_count: int


class ScoresResponse(BaseModel):
    city: str
    count: int
    stats: CityStats
    features: list[dict[str, Any]]


class RadioDetail(BaseModel):
    link: str
    city: str
    properties: dict[str, Any]
