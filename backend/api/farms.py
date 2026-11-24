from __future__ import annotations

import json
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.farm import Farm
from backend.models.field import Field
from backend.models.user import User
from backend.schemas.farm import FarmResponse, FarmUpdate
from backend.utils.geo import calculate_area_ha, find_centroid

router = APIRouter()


class FarmCreateInput(BaseModel):
    name: str
    location_description: Optional[str] = None
    center_lat: float = 23.0775
    center_lng: float = 76.8513
    total_area_ha: Optional[float] = None
    user_id: Optional[int] = None
    boundary_geojson: Optional[Any] = None


def _serialize_field(f: Field) -> dict:
    try:
        geom = json.loads(f.boundary_geojson) if isinstance(f.boundary_geojson, str) else f.boundary_geojson
    except Exception:
        geom = f.boundary_geojson
    return {
        "id": f.id,
        "farm_id": f.farm_id,
        "name": f.name,
        "boundary_geojson": geom,
        "crop_type": f.crop_type,
        "growth_stage": f.growth_stage,
        "area_ha": f.area_ha,
        "created_at": f.created_at.isoformat() if f.created_at else None,
    }


def _serialize_farm(farm: Farm) -> dict:
    return {
        "id": farm.id,
        "user_id": farm.user_id,
        "name": farm.name,
        "location_description": farm.location_description,
        "center_lat": farm.center_lat,
        "center_lng": farm.center_lng,
        "total_area_ha": farm.total_area_ha,
        "created_at": farm.created_at.isoformat() if farm.created_at else None,
        "fields": [_serialize_field(f) for f in (farm.fields or [])],
    }


@router.get("/farms")
def list_farms(db: Session = Depends(get_db)):
    farms = db.query(Farm).all()
    return [_serialize_farm(f) for f in farms]


@router.post("/farms")
def create_farm(farm: FarmCreateInput, db: Session = Depends(get_db)):
    user_id = farm.user_id
    if not user_id:
        first_user = db.query(User).first()
        user_id = first_user.id if first_user else 1

    center_lat = farm.center_lat
    center_lng = farm.center_lng
    total_area = farm.total_area_ha

    boundary_str = None
    if farm.boundary_geojson:
        boundary_str = (
            farm.boundary_geojson
            if isinstance(farm.boundary_geojson, str)
            else json.dumps(farm.boundary_geojson)
        )
        try:
            center_lat, center_lng = find_centroid(boundary_str)
            if total_area is None:
                total_area = round(calculate_area_ha(boundary_str), 2)
        except Exception:
            pass

    db_farm = Farm(
        user_id=user_id,
        name=farm.name,
        location_description=farm.location_description,
        center_lat=center_lat,
        center_lng=center_lng,
        total_area_ha=total_area,
    )
    db.add(db_farm)
    db.commit()
    db.refresh(db_farm)

    if boundary_str:
        default_field = Field(
            farm_id=db_farm.id,
            name=f"{farm.name} - Main Field",
            boundary_geojson=boundary_str,
            crop_type="Wheat",
            growth_stage="Vegetative",
            area_ha=total_area or 10.0,
        )
        db.add(default_field)
        db.commit()
        db.refresh(db_farm)

    return _serialize_farm(db_farm)


@router.get("/farms/{farm_id}")
def get_farm(farm_id: int, db: Session = Depends(get_db)):
    farm = db.query(Farm).filter(Farm.id == farm_id).first()
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")
    return _serialize_farm(farm)


@router.put("/farms/{farm_id}", response_model=FarmResponse)
def update_farm(farm_id: int, farm_update: FarmUpdate, db: Session = Depends(get_db)):
    farm = db.query(Farm).filter(Farm.id == farm_id).first()
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")
    for k, v in farm_update.dict(exclude_unset=True).items():
        setattr(farm, k, v)
    db.commit()
    db.refresh(farm)
    return farm


@router.delete("/farms/{farm_id}")
def delete_farm(farm_id: int, db: Session = Depends(get_db)):
    farm = db.query(Farm).filter(Farm.id == farm_id).first()
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")
    db.delete(farm)
    db.commit()
    return {"deleted": True, "id": farm_id}
