import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.database import init_db
from backend.api import users, farms, fields, satellite, hotspots, soil_samples, recommendations, reports, dashboard
from backend.services.gee_service import get_gee_service

app = FastAPI(title="EPICS Farm Scouting API")

import os

# Allow localhost for dev, plus any Vercel deployment URL
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
]
# Add production Vercel URL from env if set
vercel_url = os.getenv("FRONTEND_URL", "")
if vercel_url:
    ALLOWED_ORIGINS.append(vercel_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    init_db()
    gee = get_gee_service()
    gee.initialize()

@app.get("/health")
def health_check():
    return {"status": "ok"}

app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(farms.router, prefix="/api/farms", tags=["farms"])
app.include_router(fields.router, prefix="/api/fields", tags=["fields"])
app.include_router(satellite.router, prefix="/api", tags=["satellite"]) # includes /fields/{id}/analyze
app.include_router(hotspots.router, prefix="/api/hotspots", tags=["hotspots"])
app.include_router(soil_samples.router, prefix="/api/soil-samples", tags=["soil_samples"])
app.include_router(recommendations.router, prefix="/api/recommendations", tags=["recommendations"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
app.include_router(dashboard.router, prefix="/api", tags=["dashboard"])
