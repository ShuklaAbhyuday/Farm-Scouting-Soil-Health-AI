"""Dashboard API — aggregated field health summary."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.field import Field
from backend.models.hotspot import Hotspot
from backend.models.satellite import SatelliteObservation, IndexResult
from backend.models.recommendation import Recommendation

router = APIRouter()


@router.get("/fields/{field_id}/dashboard")
def get_dashboard(field_id: int, db: Session = Depends(get_db)):
    """Return an aggregated dashboard summary for a field."""
    field = db.query(Field).filter(Field.id == field_id).first()
    if not field:
        return {"error": "Field not found"}

    # Latest observation
    latest_obs = (
        db.query(SatelliteObservation)
        .filter(SatelliteObservation.field_id == field_id, SatelliteObservation.status == "processed")
        .order_by(SatelliteObservation.acquisition_date.desc())
        .first()
    )

    # Hotspots for the field
    hotspots = db.query(Hotspot).filter(Hotspot.field_id == field_id).all()
    critical_hotspots = [h for h in hotspots if h.severity == "severe"]

    # Latest index values
    ndvi_mean = ndmi_mean = ndre_mean = None
    latest_date = None
    if latest_obs:
        latest_date = latest_obs.acquisition_date.isoformat() if latest_obs.acquisition_date else None
        indices = db.query(IndexResult).filter(IndexResult.observation_id == latest_obs.id).all()
        for idx in indices:
            if idx.index_type == "NDVI":
                ndvi_mean = idx.mean_value
            elif idx.index_type == "NDMI":
                ndmi_mean = idx.mean_value
            elif idx.index_type == "NDRE":
                ndre_mean = idx.mean_value

    # Overall health score (average of hotspot scores or default)
    if hotspots:
        avg_score = sum(h.health_score for h in hotspots) / len(hotspots)
    else:
        avg_score = 85.0  # default healthy when no hotspots detected

    # Determine overall health label
    if avg_score >= 80:
        overall_health = "Healthy"
    elif avg_score >= 60:
        overall_health = "Mild Stress"
    elif avg_score >= 40:
        overall_health = "Moderate Stress"
    else:
        overall_health = "Severe Stress"

    # NDVI trend from last 3 observations
    ndvi_trend = "stable"
    recent_obs = (
        db.query(SatelliteObservation)
        .filter(SatelliteObservation.field_id == field_id, SatelliteObservation.status == "processed")
        .order_by(SatelliteObservation.acquisition_date.desc())
        .limit(3)
        .all()
    )
    if len(recent_obs) >= 2:
        ndvi_values = []
        for obs in recent_obs:
            idx = db.query(IndexResult).filter(
                IndexResult.observation_id == obs.id, IndexResult.index_type == "NDVI"
            ).first()
            if idx:
                ndvi_values.append(idx.mean_value)
        if len(ndvi_values) >= 2:
            if ndvi_values[0] > ndvi_values[-1] + 0.03:
                ndvi_trend = "improving"
            elif ndvi_values[0] < ndvi_values[-1] - 0.03:
                ndvi_trend = "declining"

    # Recent recommendations
    recent_recs = (
        db.query(Recommendation)
        .filter(Recommendation.field_id == field_id)
        .order_by(Recommendation.created_at.desc())
        .limit(5)
        .all()
    )

    # Highest priority hotspot
    highest_priority = None
    if hotspots:
        sorted_hs = sorted(hotspots, key=lambda h: h.health_score)
        highest_priority = {
            "id": sorted_hs[0].id,
            "severity": sorted_hs[0].severity,
            "health_score": sorted_hs[0].health_score,
            "likely_issue": sorted_hs[0].likely_issue,
            "explanation": sorted_hs[0].explanation,
            "detection_method": sorted_hs[0].detection_method,
        }

    return {
        "field_name": field.name,
        "crop_type": field.crop_type,
        "growth_stage": field.growth_stage,
        "area_ha": field.area_ha,
        "latest_observation_date": latest_date,
        "overall_health": overall_health,
        "health_score": round(avg_score, 1),
        "total_hotspots": len(hotspots),
        "critical_hotspots": len(critical_hotspots),
        "ndvi_mean": round(ndvi_mean, 4) if ndvi_mean is not None else None,
        "ndmi_mean": round(ndmi_mean, 4) if ndmi_mean is not None else None,
        "ndre_mean": round(ndre_mean, 4) if ndre_mean is not None else None,
        "ndvi_trend": ndvi_trend,
        "recent_recommendations": [
            {
                "id": r.id,
                "category": r.category,
                "title": r.title,
                "description": r.description,
                "priority": r.priority,
                "confidence": r.confidence,
                "requires_ground_truth": r.requires_ground_truth,
            }
            for r in recent_recs
        ],
        "highest_priority_hotspot": highest_priority,
    }
