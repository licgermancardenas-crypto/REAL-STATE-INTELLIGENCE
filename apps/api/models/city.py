from pydantic import BaseModel


class CityOut(BaseModel):
    id: str
    name: str
    lat: float
    lon: float
    zoom: int
