from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from routers import cities, zones, alpha, listings

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cities.router, prefix="/api/cities", tags=["cities"])
app.include_router(zones.router, prefix="/api/zones", tags=["zones"])
app.include_router(alpha.router, prefix="/api/alpha", tags=["alpha"])
app.include_router(listings.router, prefix="/api/listings", tags=["listings"])


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
