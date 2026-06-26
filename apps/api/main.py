"""
RSI FastAPI — Real State Intelligence API
Serve: uvicorn apps.api.main:app --reload
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import scores, radios, cities

app = FastAPI(
    title="RSI — Real State Intelligence API",
    version="0.2.0",
    description="Alpha Score por radio censal · Buenos Aires",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(scores.router,  prefix="/api/v1")
app.include_router(radios.router,  prefix="/api/v1")
app.include_router(cities.router,  prefix="/api/v1")


@app.get("/")
def root():
    return {
        "name": "RSI API",
        "version": "0.2.0",
        "endpoints": [
            "GET /api/v1/cities/",
            "GET /api/v1/scores/{city}",
            "GET /api/v1/scores/{city}/stats",
            "GET /api/v1/scores/{city}/top",
            "GET /api/v1/radios/{link}",
        ],
    }


@app.get("/health")
def health():
    return {"status": "ok"}
