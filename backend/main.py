import os
import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.database import init_db, SessionLocal
from backend.api import users, farms, fields, satellite, hotspots, soil_samples, recommendations, reports, dashboard
from backend.services.gee_service import get_gee_service
from backend.models.user import User
from backend.models.farm import Farm
from backend.models.field import Field

app = FastAPI(title="EPICS Farm Scouting API")

# Allow localhost for dev, plus any Vercel deployment URL
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
]
vercel_url = os.getenv("FRONTEND_URL", "")
if vercel_url:
    ALLOWED_ORIGINS.append(vercel_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def seed_default_data():
    """Ensure a default demo user, farm, and field (id=1) exist on fresh deploys."""
    db = SessionLocal()
    try:
        if db.query(Field).first() is not None:
            return
        user = db.query(User).first()
        if not user:
            user = User(email="demo@farmscout.ai", name="Demo Farmer")
            db.add(user)
            db.commit()
            db.refresh(user)
        farm = db.query(Farm).first()
        if not farm:
            farm = Farm(
                user_id=user.id,
                name="Demo Farm",
                location_description="VIT Bhopal Demo Plot",
                center_lat=23.0775,
                center_lng=76.8513,
                total_area_ha=12.5,
            )
            db.add(farm)
            db.commit()
            db.refresh(farm)
        demo_poly = {
            "type": "Polygon",
            "coordinates": [[
                [76.849, 23.076],
                [76.853, 23.076],
                [76.853, 23.079],
                [76.849, 23.079],
                [76.849, 23.076],
            ]],
        }
        field = Field(
            farm_id=farm.id,
            name="North Wheat Plot",
            boundary_geojson=json.dumps(demo_poly),
            crop_type="Wheat",
            growth_stage="Vegetative",
            area_ha=12.5,
        )
        db.add(field)
        db.commit()
    finally:
        db.close()


@app.on_event("startup")
def on_startup():
    init_db()
    seed_default_data()
    gee = get_gee_service()
    gee.initialize()

@app.get("/health")
def health_check():
    return {"status": "ok"}

app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(farms.router, prefix="/api", tags=["farms"])
app.include_router(fields.router, prefix="/api", tags=["fields"])
app.include_router(satellite.router, prefix="/api", tags=["satellite"])
app.include_router(hotspots.router, prefix="/api", tags=["hotspots"])
app.include_router(soil_samples.router, prefix="/api", tags=["soil_samples"])
app.include_router(recommendations.router, prefix="/api", tags=["recommendations"])
app.include_router(reports.router, prefix="/api", tags=["reports"])
app.include_router(dashboard.router, prefix="/api", tags=["dashboard"])
