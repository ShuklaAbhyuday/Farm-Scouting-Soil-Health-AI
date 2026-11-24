from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.field import Field
from backend.models.recommendation import Recommendation
from backend.models.satellite import SatelliteObservation, IndexResult
from backend.models.soil_sample import SoilSample
from backend.schemas.recommendation import RecommendationCreate, RecommendationResponse
from backend.services.recommendation_service import RecommendationService

router = APIRouter()


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

    # Clear old auto-generated recs for clean regeneration
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
