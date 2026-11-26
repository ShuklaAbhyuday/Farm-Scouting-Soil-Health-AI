from __future__ import annotations

import json
from datetime import datetime
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

    all_active = (
        db.query(SatelliteObservation)
        .filter(
            SatelliteObservation.field_id == field_id,
            SatelliteObservation.is_superseded == False,
        )
        .order_by(SatelliteObservation.acquisition_date.asc(), SatelliteObservation.id.asc())
        .all()
    )

    # Never contaminate real Sentinel-2 phenology with demo observations
    real_optical = [o for o in all_active if not o.is_demo and o.source == "sentinel-2"]
    if real_optical:
        observations = real_optical
    else:
        observations = [o for o in all_active if o.is_demo]

    dates, ndvi, evi, savi, gndvi, ndmi, ndre, health_scores, records = [], [], [], [], [], [], [], [], []
    seen_days = set()
    for obs in observations:
        indices = db.query(IndexResult).filter(IndexResult.observation_id == obs.id).all()
        idx_map = {i.index_type.upper(): i.mean_value for i in indices if i.mean_value is not None}
        if "NDVI" not in idx_map:
            continue

        date_str = obs.acquisition_date.strftime("%Y-%m-%d") if obs.acquisition_date else ""
        if date_str in seen_days:
            continue
        seen_days.add(date_str)

        def _opt(key: str):
            val = idx_map.get(key)
            return round(float(val), 4) if val is not None else None

        ndvi_v = _opt("NDVI")
        evi_v = _opt("EVI")
        savi_v = _opt("SAVI")
        gndvi_v = _opt("GNDVI")
        ndmi_v = _opt("NDMI")
        ndre_v = _opt("NDRE")

        obs_hotspots = db.query(Hotspot).filter(Hotspot.observation_id == obs.id).all()
        if obs_hotspots:
            score = round(sum(h.health_score for h in obs_hotspots) / len(obs_hotspots), 1)
        elif ndvi_v is not None and ndmi_v is not None and ndre_v is not None:
            score = round(min(100.0, max(0.0, (0.4 * ndvi_v + 0.35 * ((ndmi_v + 1) / 2) + 0.25 * ndre_v) * 120)), 1)
        else:
            score = None

        meta = {}
        if obs.bands_metadata:
            try:
                parsed = json.loads(obs.bands_metadata)
                if isinstance(parsed, dict):
                    meta = parsed
            except Exception:
                pass

        ts_prec = (
            "simulated" if obs.is_demo else (
                "approximate" if meta.get("timestamp_precision") == "migrated_legacy_approximate_day" else (
                    "composite_window" if (obs.composite_method or meta.get("composite_method")) == "10d_median_composite" else "exact"
                )
            )
        )

        dates.append(date_str)
        ndvi.append(ndvi_v)
        evi.append(evi_v)
        savi.append(savi_v)
        gndvi.append(gndvi_v)
        ndmi.append(ndmi_v)
        ndre.append(ndre_v)
        health_scores.append(score)
        records.append({
            "observation_id": obs.id,
            "source": obs.source,
            "collection_id": obs.collection_id,
            "image_id": obs.image_id,
            "is_demo": bool(obs.is_demo),
            "timestamp_precision": ts_prec,
            "date": date_str,
            "ndvi": ndvi_v,
            "evi": evi_v,
            "savi": savi_v,
            "gndvi": gndvi_v,
            "ndmi": ndmi_v,
            "ndre": ndre_v,
            "cloud_cover_pct": round(obs.cloud_cover_pct, 2) if obs.cloud_cover_pct is not None else None,
            "valid_pixel_pct": (
                round(obs.valid_pixel_pct, 2)
                if obs.valid_pixel_pct is not None
                else meta.get("valid_pixel_pct")
            ),
            "observation_count": (
                obs.observation_count
                if obs.observation_count is not None
                else meta.get("observation_count")
            ),
            "composite_method": obs.composite_method or meta.get("composite_method"),
            "composite_period_start": meta.get("composite_period_start"),
            "composite_period_end": meta.get("composite_period_end"),
            "health_score": score,
            "hotspot_count": len(obs_hotspots),
        })

    gap_periods = []
    for i in range(1, len(dates)):
        d_prev = datetime.strptime(dates[i - 1], "%Y-%m-%d")
        d_cur = datetime.strptime(dates[i], "%Y-%m-%d")
        delta_d = (d_cur - d_prev).days
        if delta_d > 15:
            gap_periods.append({
                "after_date": dates[i - 1],
                "before_date": dates[i],
                "gap_days": delta_d,
            })

    return {
        "dates": dates,
        "ndvi": ndvi,
        "evi": evi,
        "savi": savi,
        "gndvi": gndvi,
        "ndmi": ndmi,
        "ndre": ndre,
        "health_scores": health_scores,
        "observations": records,
        "missing_gap_periods": gap_periods,
    }
