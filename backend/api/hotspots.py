from __future__ import annotations

import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.hotspot import Hotspot
from backend.schemas.hotspot import HotspotCreate

router = APIRouter()


def _serialize_hotspot(h: Hotspot) -> dict:
    try:
        geom = json.loads(h.geometry_geojson) if isinstance(h.geometry_geojson, str) else h.geometry_geojson
    except Exception:
        geom = h.geometry_geojson
    return {
        "id": h.id,
        "field_id": h.field_id,
        "observation_id": h.observation_id,
        "geometry_geojson": geom,
        "center_lat": h.center_lat,
        "center_lng": h.center_lng,
        "area_ha": h.area_ha,
        "severity": h.severity,
        "health_score": h.health_score,
        "ndvi_value": h.ndvi_value,
        "ndmi_value": h.ndmi_value,
        "ndre_value": h.ndre_value,
        "ndvi_deviation": h.ndvi_deviation,
        "ndmi_deviation": h.ndmi_deviation,
        "ndre_deviation": h.ndre_deviation,
        "likely_issue": h.likely_issue,
        "explanation": h.explanation,
        "detection_method": h.detection_method,
        "persistence_count": h.persistence_count,
        "is_active": h.is_active,
        "first_detected": h.first_detected.isoformat() if h.first_detected else None,
        "created_at": h.created_at.isoformat() if h.created_at else None,
    }


@router.get("/fields/{field_id}/hotspots")
def list_field_hotspots(field_id: int, include_historical: bool = False, db: Session = Depends(get_db)):
    q = db.query(Hotspot).filter(Hotspot.field_id == field_id)
    if not include_historical:
        q = q.filter(Hotspot.is_active == True)
    hotspots = q.order_by(Hotspot.health_score.asc(), Hotspot.id.desc()).all()
    return [_serialize_hotspot(h) for h in hotspots]


@router.get("/fields/{field_id}/hotspots/summary")
def hotspot_summary(field_id: int, db: Session = Depends(get_db)):
    hotspots = db.query(Hotspot).filter(Hotspot.field_id == field_id, Hotspot.is_active == True).all()
    counts = {"healthy": 0, "mild": 0, "moderate": 0, "severe": 0}
    for h in hotspots:
        counts[h.severity] = counts.get(h.severity, 0) + 1
    return {"total": len(hotspots), "by_severity": counts}


@router.post("/hotspots")
def create_hotspot(hotspot: HotspotCreate, db: Session = Depends(get_db)):
    db_hotspot = Hotspot(**hotspot.dict())
    db.add(db_hotspot)
    db.commit()
    db.refresh(db_hotspot)
    return _serialize_hotspot(db_hotspot)


@router.get("/hotspots/{hotspot_id}")
def get_hotspot(hotspot_id: int, db: Session = Depends(get_db)):
    hotspot = db.query(Hotspot).filter(Hotspot.id == hotspot_id).first()
    if not hotspot:
        raise HTTPException(status_code=404, detail="Hotspot not found")
    return _serialize_hotspot(hotspot)


@router.get("/hotspots/{hotspot_id}/history")
def get_hotspot_history(hotspot_id: int, db: Session = Depends(get_db)):
    hotspot = db.query(Hotspot).filter(Hotspot.id == hotspot_id).first()
    if not hotspot:
        raise HTTPException(status_code=404, detail="Hotspot not found")
    related = (
        db.query(Hotspot)
        .filter(Hotspot.field_id == hotspot.field_id)
        .order_by(Hotspot.created_at.desc())
        .limit(20)
        .all()
    )
    return [_serialize_hotspot(h) for h in related]
