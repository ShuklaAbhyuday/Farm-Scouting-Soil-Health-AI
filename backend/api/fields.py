from __future__ import annotations

import json
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.farm import Farm
from backend.models.field import Field
from backend.models.hotspot import Hotspot
from backend.models.satellite import SatelliteObservation, IndexResult
from backend.schemas.field import FieldUpdate
from backend.utils.geo import calculate_area_ha

router = APIRouter()


class FieldCreateInput(BaseModel):
    name: str
    boundary_geojson: Any
    crop_type: Optional[str] = "Wheat"
    growth_stage: Optional[str] = "Vegetative"
    area_ha: Optional[float] = None
    farm_id: Optional[int] = None


def _serialize_field(field: Field) -> dict:
    try:
        geom = json.loads(field.boundary_geojson) if isinstance(field.boundary_geojson, str) else field.boundary_geojson
    except Exception:
        geom = field.boundary_geojson
    return {
        "id": field.id,
        "farm_id": field.farm_id,
        "name": field.name,
        "boundary_geojson": geom,
        "crop_type": field.crop_type,
        "growth_stage": field.growth_stage,
        "area_ha": field.area_ha,
        "created_at": field.created_at.isoformat() if field.created_at else None,
    }


@router.get("/fields")
def list_all_fields(db: Session = Depends(get_db)):
    fields = db.query(Field).all()
    return [_serialize_field(f) for f in fields]


@router.get("/farms/{farm_id}/fields")
def list_farm_fields(farm_id: int, db: Session = Depends(get_db)):
    fields = db.query(Field).filter(Field.farm_id == farm_id).all()
    return [_serialize_field(f) for f in fields]


@router.post("/farms/{farm_id}/fields")
def create_farm_field(farm_id: int, payload: FieldCreateInput, db: Session = Depends(get_db)):
    farm = db.query(Farm).filter(Farm.id == farm_id).first()
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")

    boundary_str = (
        payload.boundary_geojson
        if isinstance(payload.boundary_geojson, str)
        else json.dumps(payload.boundary_geojson)
    )
    area_ha = payload.area_ha
    if area_ha is None:
        try:
            area_ha = round(max(0.1, calculate_area_ha(boundary_str)), 2)
        except Exception:
            area_ha = 5.0

    db_field = Field(
        farm_id=farm_id,
        name=payload.name,
        boundary_geojson=boundary_str,
        crop_type=payload.crop_type,
        growth_stage=payload.growth_stage,
        area_ha=area_ha,
    )
    db.add(db_field)
    db.commit()
    db.refresh(db_field)
    return _serialize_field(db_field)


@router.post("/fields")
def create_field(payload: FieldCreateInput, db: Session = Depends(get_db)):
    farm_id = payload.farm_id
    if not farm_id:
        first_farm = db.query(Farm).first()
        if not first_farm:
            raise HTTPException(status_code=404, detail="No farm exists")
        farm_id = first_farm.id
    return create_farm_field(farm_id, payload, db)


@router.get("/fields/{field_id}")
def get_field(field_id: int, db: Session = Depends(get_db)):
    field = db.query(Field).filter(Field.id == field_id).first()
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")
    return _serialize_field(field)


@router.put("/fields/{field_id}")
def update_field(field_id: int, payload: FieldUpdate, db: Session = Depends(get_db)):
    field = db.query(Field).filter(Field.id == field_id).first()
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")
    data = payload.dict(exclude_unset=True)
    if "boundary_geojson" in data and not isinstance(data["boundary_geojson"], str):
        data["boundary_geojson"] = json.dumps(data["boundary_geojson"])
    for k, v in data.items():
        setattr(field, k, v)
    db.commit()
    db.refresh(field)
    return _serialize_field(field)


@router.delete("/fields/{field_id}")
def delete_field(field_id: int, db: Session = Depends(get_db)):
    from backend.models.recommendation import Recommendation
    from backend.models.report import Report
    from backend.models.soil_sample import SoilSample

    field = db.query(Field).filter(Field.id == field_id).first()
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")

    obs_ids = [o.id for o in db.query(SatelliteObservation).filter(SatelliteObservation.field_id == field_id).all()]
    if obs_ids:
        db.query(IndexResult).filter(IndexResult.observation_id.in_(obs_ids)).delete(synchronize_session=False)
    db.query(Hotspot).filter(Hotspot.field_id == field_id).delete(synchronize_session=False)
    db.query(Recommendation).filter(Recommendation.field_id == field_id).delete(synchronize_session=False)
    db.query(SoilSample).filter(SoilSample.field_id == field_id).delete(synchronize_session=False)
    db.query(Report).filter(Report.field_id == field_id).delete(synchronize_session=False)
    db.query(SatelliteObservation).filter(SatelliteObservation.field_id == field_id).delete(synchronize_session=False)
    db.delete(field)
    db.commit()
    return {"deleted": True, "id": field_id}


@router.get("/fields/{field_id}/history")
def get_field_history(field_id: int, db: Session = Depends(get_db)):
    field = db.query(Field).filter(Field.id == field_id).first()
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")

    observations = (
        db.query(SatelliteObservation)
        .filter(SatelliteObservation.field_id == field_id)
        .order_by(SatelliteObservation.acquisition_date.asc())
        .all()
    )

    dates, ndvi, ndmi, ndre, health_scores, records = [], [], [], [], [], []
    for obs in observations:
        indices = db.query(IndexResult).filter(IndexResult.observation_id == obs.id).all()
        idx_map = {i.index_type.upper(): i.mean_value for i in indices}
        ndvi_v = round(idx_map.get("NDVI", 0.0), 4)
        ndmi_v = round(idx_map.get("NDMI", 0.0), 4)
        ndre_v = round(idx_map.get("NDRE", 0.0), 4)

        obs_hotspots = db.query(Hotspot).filter(Hotspot.observation_id == obs.id).all()
        if obs_hotspots:
            score = round(sum(h.health_score for h in obs_hotspots) / len(obs_hotspots), 1)
        else:
            score = round(min(100.0, max(0.0, (0.4 * ndvi_v + 0.35 * ((ndmi_v + 1) / 2) + 0.25 * ndre_v) * 120)), 1)

        date_str = obs.acquisition_date.strftime("%Y-%m-%d") if obs.acquisition_date else ""
        dates.append(date_str)
        ndvi.append(ndvi_v)
        ndmi.append(ndmi_v)
        ndre.append(ndre_v)
        health_scores.append(score)
        records.append({
            "observation_id": obs.id,
            "date": date_str,
            "ndvi": ndvi_v,
            "ndmi": ndmi_v,
            "ndre": ndre_v,
            "cloud_cover_pct": round(obs.cloud_cover_pct or 0.0, 2),
            "health_score": score,
            "hotspot_count": len(obs_hotspots),
        })

    return {
        "dates": dates,
        "ndvi": ndvi,
        "ndmi": ndmi,
        "ndre": ndre,
        "health_scores": health_scores,
        "observations": records,
    }
