from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.field import Field
from backend.models.recommendation import Recommendation
from backend.models.satellite import SatelliteObservation, IndexResult
from backend.models.soil_sample import SoilSample
from backend.schemas.recommendation import RecommendationCreate, RecommendationResponse
from backend.services.crop_recommendation_service import recommend_crops
from backend.services.recommendation_service import RecommendationService

router = APIRouter()


class CropRecommendationInput(BaseModel):
    nitrogen_value: Optional[float] = None
    nitrogen_level: Optional[str] = None
    phosphorus_value: Optional[float] = None
    phosphorus_level: Optional[str] = None
    potassium_value: Optional[float] = None
    potassium_level: Optional[str] = None
    ph_value: Optional[float] = None
    moisture_level: Optional[str] = None
    soil_texture: Optional[str] = None
    season: str = "All"
    use_latest_sample: bool = True


def _compute_crop_recommendation(
    field_id: int,
    payload: Optional[CropRecommendationInput],
    db: Session,
) -> dict:
    field = db.query(Field).filter(Field.id == field_id).first()
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")

    latest_sample = (
        db.query(SoilSample)
        .filter(SoilSample.field_id == field_id)
        .order_by(SoilSample.created_at.desc())
        .first()
    )

    latest_obs = (
        db.query(SatelliteObservation)
        .filter(SatelliteObservation.field_id == field_id)
        .order_by(SatelliteObservation.acquisition_date.desc())
        .first()
    )
    ndmi_mean = None
    if latest_obs:
        ndmi_idx = (
            db.query(IndexResult)
            .filter(IndexResult.observation_id == latest_obs.id, IndexResult.index_type == "NDMI")
            .first()
        )
        if ndmi_idx:
            ndmi_mean = ndmi_idx.mean_value

    use_sample = latest_sample is not None and (payload is None or payload.use_latest_sample)

    n_val = payload.nitrogen_value if (payload and payload.nitrogen_value is not None) else (latest_sample.nitrogen_value if use_sample else None)
    n_lvl = payload.nitrogen_level if (payload and payload.nitrogen_level) else (latest_sample.nitrogen_level if use_sample else "medium")
    p_val = payload.phosphorus_value if (payload and payload.phosphorus_value is not None) else (latest_sample.phosphorus_value if use_sample else None)
    p_lvl = payload.phosphorus_level if (payload and payload.phosphorus_level) else (latest_sample.phosphorus_level if use_sample else "medium")
    k_val = payload.potassium_value if (payload and payload.potassium_value is not None) else (latest_sample.potassium_value if use_sample else None)
    k_lvl = payload.potassium_level if (payload and payload.potassium_level) else (latest_sample.potassium_level if use_sample else "medium")
    ph_val = payload.ph_value if (payload and payload.ph_value is not None) else ((latest_sample.ph_value if use_sample and latest_sample.ph_value is not None else 6.8))
    moisture = payload.moisture_level if (payload and payload.moisture_level) else ((latest_sample.moisture_level if use_sample and latest_sample.moisture_level else "medium"))
    texture = payload.soil_texture if (payload and payload.soil_texture) else ((latest_sample.soil_texture if use_sample and latest_sample.soil_texture else "Loamy"))
    season = payload.season if payload else "All"

    is_validated = bool(use_sample and latest_sample and latest_sample.is_validated)
    source_mode = (
        "validated_soil_sample"
        if is_validated
        else ("unvalidated_soil_sample" if use_sample else "manual_or_satellite_estimate")
    )

    crops = recommend_crops(
        nitrogen_value=n_val,
        nitrogen_level=n_lvl,
        phosphorus_value=p_val,
        phosphorus_level=p_lvl,
        potassium_value=k_val,
        potassium_level=k_lvl,
        ph_value=ph_val,
        moisture_level=moisture,
        soil_texture=texture,
        season=season,
        ndmi_mean=ndmi_mean,
        is_validated=is_validated,
    )

    return {
        "field_id": field_id,
        "field_name": field.name,
        "current_crop": field.crop_type,
        "source_mode": source_mode,
        "has_soil_sample": latest_sample is not None,
        "is_validated": is_validated,
        "inputs_used": {
            "nitrogen_value": n_val,
            "nitrogen_level": n_lvl,
            "phosphorus_value": p_val,
            "phosphorus_level": p_lvl,
            "potassium_value": k_val,
            "potassium_level": k_lvl,
            "ph_value": ph_val,
            "moisture_level": moisture,
            "soil_texture": texture,
            "season": season,
            "ndmi_mean": round(ndmi_mean, 4) if ndmi_mean is not None else None,
        },
        "recommendations": crops,
    }


@router.get("/fields/{field_id}/crop-recommendation")
def get_crop_recommendation(field_id: int, db: Session = Depends(get_db)):
    return _compute_crop_recommendation(field_id, None, db)


@router.post("/fields/{field_id}/crop-recommendation")
def post_crop_recommendation(
    field_id: int,
    payload: Optional[CropRecommendationInput] = None,
    db: Session = Depends(get_db),
):
    return _compute_crop_recommendation(field_id, payload, db)


def generate_and_store_recommendations(field_id: int, db: Session) -> list[Recommendation]:
    field = db.query(Field).filter(Field.id == field_id).first()
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")

    latest_obs = (
        db.query(SatelliteObservation)
        .filter(SatelliteObservation.field_id == field_id)
        .order_by(SatelliteObservation.acquisition_date.desc())
        .first()
    )
    satellite_data = {"NDVI_mean": 0.65, "NDMI_mean": 0.25, "NDRE_mean": 0.42}
    if latest_obs:
        indices = db.query(IndexResult).filter(IndexResult.observation_id == latest_obs.id).all()
        for idx in indices:
            satellite_data[f"{idx.index_type.upper()}_mean"] = idx.mean_value

    soil_samples = (
        db.query(SoilSample)
        .filter(SoilSample.field_id == field_id)
        .order_by(SoilSample.created_at.desc())
        .all()
    )

    rec_service = RecommendationService()
    generated = rec_service.generate_recommendation(field_id, soil_samples, satellite_data)

    db.query(Recommendation).filter(Recommendation.field_id == field_id).delete()
    db.commit()

    created = []
    for item in generated:
        db_rec = Recommendation(field_id=field_id, **item)
        db.add(db_rec)
        created.append(db_rec)
    db.commit()
    for r in created:
        db.refresh(r)
    return created


@router.get("/fields/{field_id}/recommendations", response_model=list[RecommendationResponse])
def list_field_recommendations(field_id: int, db: Session = Depends(get_db)):
    return (
        db.query(Recommendation)
        .filter(Recommendation.field_id == field_id)
        .order_by(Recommendation.created_at.desc())
        .all()
    )


@router.post("/fields/{field_id}/recommendations/generate", response_model=list[RecommendationResponse])
def generate_field_recommendations(field_id: int, db: Session = Depends(get_db)):
    return generate_and_store_recommendations(field_id, db)


@router.post("/recommendations", response_model=RecommendationResponse)
def create_recommendation(recommendation: RecommendationCreate, db: Session = Depends(get_db)):
    db_rec = Recommendation(**recommendation.dict())
    db.add(db_rec)
    db.commit()
    db.refresh(db_rec)
    return db_rec


@router.get("/recommendations/{rec_id}", response_model=RecommendationResponse)
def get_recommendation(rec_id: int, db: Session = Depends(get_db)):
    rec = db.query(Recommendation).filter(Recommendation.id == rec_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return rec
