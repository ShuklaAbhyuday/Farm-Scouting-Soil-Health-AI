from __future__ import annotations

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.field import Field
from backend.models.soil_sample import SoilSample
from backend.schemas.soil_sample import SoilSampleUpdate
from backend.services.crop_recommendation_service import analyze_soil_sample
from backend.utils.geo import find_centroid

router = APIRouter()


class SoilSampleInput(BaseModel):
    field_id: Optional[int] = None
    hotspot_id: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    nitrogen_level: Optional[str] = "medium"
    nitrogen_value: Optional[float] = None
    phosphorus_level: Optional[str] = "medium"
    phosphorus_value: Optional[float] = None
    potassium_level: Optional[str] = "medium"
    potassium_value: Optional[float] = None
    ph_value: Optional[float] = 7.0
    moisture_level: Optional[str] = "medium"
    moisture_value: Optional[float] = None
    soil_texture: Optional[str] = "Loamy"
    sample_date: Optional[datetime] = None
    source: str = "manual"
    is_validated: bool = False
    notes: Optional[str] = None


def _serialize_sample(s: SoilSample) -> dict:
    return {
        "id": s.id,
        "field_id": s.field_id,
        "hotspot_id": s.hotspot_id,
        "latitude": s.latitude,
        "longitude": s.longitude,
        "nitrogen_level": s.nitrogen_level,
        "nitrogen_value": s.nitrogen_value,
        "phosphorus_level": s.phosphorus_level,
        "phosphorus_value": s.phosphorus_value,
        "potassium_level": s.potassium_level,
        "potassium_value": s.potassium_value,
        "ph_value": s.ph_value,
        "moisture_level": s.moisture_level,
        "moisture_value": s.moisture_value,
        "soil_texture": s.soil_texture,
        "sample_date": s.sample_date.isoformat() if s.sample_date else None,
        "source": s.source,
        "is_validated": s.is_validated,
        "notes": s.notes,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "analysis": analyze_soil_sample(s),
    }


def _create_sample_for_field(field_id: int, sample: SoilSampleInput, db: Session) -> SoilSample:
    field = db.query(Field).filter(Field.id == field_id).first()
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")

    lat, lng = sample.latitude, sample.longitude
    if lat is None or lng is None:
        try:
            lat, lng = find_centroid(field.boundary_geojson)
        except Exception:
            lat, lng = 23.0775, 76.8513

    db_sample = SoilSample(
        field_id=field_id,
        hotspot_id=sample.hotspot_id,
        latitude=lat,
        longitude=lng,
        nitrogen_level=sample.nitrogen_level,
        nitrogen_value=sample.nitrogen_value,
        phosphorus_level=sample.phosphorus_level,
        phosphorus_value=sample.phosphorus_value,
        potassium_level=sample.potassium_level,
        potassium_value=sample.potassium_value,
        ph_value=sample.ph_value,
        moisture_level=sample.moisture_level,
        moisture_value=sample.moisture_value,
        soil_texture=sample.soil_texture,
        sample_date=sample.sample_date or datetime.utcnow(),
        source=sample.source,
        is_validated=sample.is_validated,
        notes=sample.notes,
    )
    db.add(db_sample)
    db.commit()
    db.refresh(db_sample)
    return db_sample


@router.get("/fields/{field_id}/soil-samples")
def list_soil_samples(field_id: int, db: Session = Depends(get_db)):
    samples = (
        db.query(SoilSample)
        .filter(SoilSample.field_id == field_id)
        .order_by(SoilSample.created_at.desc())
        .all()
    )
    return [_serialize_sample(s) for s in samples]


@router.post("/fields/{field_id}/soil-samples")
def create_field_soil_sample(field_id: int, sample: SoilSampleInput, db: Session = Depends(get_db)):
    created = _create_sample_for_field(field_id, sample, db)
    return _serialize_sample(created)


@router.post("/soil-samples")
def create_soil_sample(sample: SoilSampleInput, db: Session = Depends(get_db)):
    created = _create_sample_for_field(sample.field_id or 1, sample, db)
    return _serialize_sample(created)


@router.get("/soil-samples/{sample_id}")
def get_soil_sample(sample_id: int, db: Session = Depends(get_db)):
    sample = db.query(SoilSample).filter(SoilSample.id == sample_id).first()
    if not sample:
        raise HTTPException(status_code=404, detail="SoilSample not found")
    return _serialize_sample(sample)


@router.put("/soil-samples/{sample_id}")
def update_soil_sample(sample_id: int, update: SoilSampleUpdate, db: Session = Depends(get_db)):
    sample = db.query(SoilSample).filter(SoilSample.id == sample_id).first()
    if not sample:
        raise HTTPException(status_code=404, detail="SoilSample not found")
    for k, v in update.dict(exclude_unset=True).items():
        setattr(sample, k, v)
    db.commit()
    db.refresh(sample)
    return _serialize_sample(sample)


@router.delete("/soil-samples/{sample_id}")
def delete_soil_sample(sample_id: int, db: Session = Depends(get_db)):
    sample = db.query(SoilSample).filter(SoilSample.id == sample_id).first()
    if not sample:
        raise HTTPException(status_code=404, detail="SoilSample not found")
    db.delete(sample)
    db.commit()
    return {"deleted": True, "id": sample_id}
