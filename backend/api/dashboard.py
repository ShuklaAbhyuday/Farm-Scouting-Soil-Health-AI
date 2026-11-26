"""Dashboard API — aggregated field health, radar wetness, and phenology summary."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.field import Field
from backend.models.hotspot import Hotspot
from backend.models.satellite import SatelliteObservation, IndexResult
from backend.models.recommendation import Recommendation

router = APIRouter()


def compute_phenology_summary(observations: list[SatelliteObservation], db: Session) -> dict:
    """Derive crop growth stage, peak vigor, and active/fallow status from Sentinel-2 time series."""
    points = []
    for obs in observations:
        ndvi_row = (
            db.query(IndexResult)
            .filter(IndexResult.observation_id == obs.id, IndexResult.index_type == "NDVI")
            .first()
        )
        if ndvi_row and obs.acquisition_date:
            points.append((obs.acquisition_date, float(ndvi_row.mean_value)))

    if not points:
        return {
            "stage": "No data",
            "land_status": "Unknown",
            "peak_ndvi": None,
            "peak_date": None,
            "observation_count": 0,
            "ndvi_change": None,
        }

    points.sort(key=lambda x: x[0])
    peak_dt, peak_val = max(points, key=lambda x: x[1])
    latest_dt, latest_val = points[-1]

    if latest_val < 0.22:
        land_status = "Bare Soil / Fallow or Early Emergence"
    elif latest_val < 0.40:
        land_status = "Sparse / Developing Canopy"
    else:
        land_status = "Active Vegetated Crop"

    ndvi_change = round(latest_val - points[-2][1], 4) if len(points) >= 2 else 0.0

    if latest_val < 0.20:
        stage = "Fallow / Pre-Emergence"
    elif len(points) >= 2 and ndvi_change > 0.04:
        stage = "Vegetative Green-Up"
    elif latest_val >= peak_val - 0.05 and latest_val >= 0.45:
        stage = "Peak Canopy Vigor"
    elif len(points) >= 2 and ndvi_change < -0.04:
        stage = "Senescence / Harvest Window"
    else:
        stage = "Mid-Season Steady"

    return {
        "stage": stage,
        "land_status": land_status,
        "peak_ndvi": round(peak_val, 4),
        "peak_date": peak_dt.strftime("%Y-%m-%d"),
        "latest_date": latest_dt.strftime("%Y-%m-%d"),
        "observation_count": len(points),
        "ndvi_change": ndvi_change,
    }


def classify_surface_wetness(s1_vv: float | None, ndmi: float | None, ndvi: float | None) -> str:
    """Interpret Sentinel-1 VV backscatter + NDMI into a plain-English surface moisture/flooding proxy."""
    if s1_vv is None:
        if ndmi is None:
            return "Unknown"
        if ndmi < -0.05:
            return "Dry Canopy Signal (Optical)"
        if ndmi > 0.35:
            return "High Canopy Moisture (Optical)"
        return "Moderate Canopy Moisture"

    # Sentinel-1 VV proxy caveats: calm open standing water reflects specularly (very low VV < -17 dB),
    # while saturated rough soil / flooded emergent vegetation elevates backscatter (VV > -7.5 dB).
    if s1_vv < -17.0 and (ndvi is None or ndvi < 0.25):
        return "Standing Water / Flooding Risk (Radar Proxy)"
    if s1_vv > -7.5:
        return "High Surface Wetness / Waterlogging Risk (Radar Proxy)"
    if s1_vv < -13.5 or (ndmi is not None and ndmi < -0.05):
        return "Dry Surface / Moisture Deficit (Radar Proxy)"
    return "Optimal Surface Moisture (Radar Proxy)"


@router.get("/fields/{field_id}/dashboard")
def get_dashboard(field_id: int, db: Session = Depends(get_db)):
    """Return an aggregated dashboard summary for a field including S2 optical, S1 radar, and phenology."""
    field = db.query(Field).filter(Field.id == field_id).first()
    if not field:
        return {"error": "Field not found"}

    all_obs = (
        db.query(SatelliteObservation)
        .filter(SatelliteObservation.field_id == field_id, SatelliteObservation.status == "processed")
        .order_by(SatelliteObservation.acquisition_date.desc())
        .all()
    )
    latest_obs = all_obs[0] if all_obs else None

    hotspots = db.query(Hotspot).filter(Hotspot.field_id == field_id).all()
    stressed_hotspots = [h for h in hotspots if h.severity != "healthy"]
    critical_hotspots = [h for h in hotspots if h.severity == "severe"]

    idx_vals: dict[str, float] = {}
    latest_date = None
    if latest_obs:
        latest_date = latest_obs.acquisition_date.isoformat() if latest_obs.acquisition_date else None
        indices = db.query(IndexResult).filter(IndexResult.observation_id == latest_obs.id).all()
        for idx in indices:
            idx_vals[idx.index_type.upper()] = idx.mean_value

    ndvi_mean = idx_vals.get("NDVI")
    evi_mean = idx_vals.get("EVI")
    savi_mean = idx_vals.get("SAVI")
    gndvi_mean = idx_vals.get("GNDVI")
    ndmi_mean = idx_vals.get("NDMI")
    ndre_mean = idx_vals.get("NDRE")
    s1_vv = idx_vals.get("S1_VV")
    s1_vh = idx_vals.get("S1_VH")
    s1_rvi = idx_vals.get("S1_RVI")

    if hotspots:
        avg_score = sum(h.health_score for h in hotspots) / len(hotspots)
    else:
        avg_score = 85.0

    if avg_score >= 80:
        overall_health = "Healthy"
    elif avg_score >= 60:
        overall_health = "Mild Stress"
    elif avg_score >= 40:
        overall_health = "Moderate Stress"
    else:
        overall_health = "Severe Stress"

    ndvi_trend = "stable"
    if len(all_obs) >= 2:
        ndvi_values = []
        for obs in all_obs[:3]:
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

    recent_recs = (
        db.query(Recommendation)
        .filter(Recommendation.field_id == field_id)
        .order_by(Recommendation.created_at.desc())
        .limit(5)
        .all()
    )

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

    phenology = compute_phenology_summary(all_obs, db)
    wetness_status = classify_surface_wetness(s1_vv, ndmi_mean, ndvi_mean)

    def _r(val, n=4):
        return round(val, n) if val is not None else None

    return {
        "field_name": field.name,
        "crop_type": field.crop_type,
        "growth_stage": field.growth_stage,
        "area_ha": field.area_ha,
        "latest_observation_date": latest_date,
        "overall_health": overall_health,
        "health_score": round(avg_score, 1),
        "total_hotspots": len(stressed_hotspots),
        "critical_hotspots": len(critical_hotspots),
        "ndvi_mean": _r(ndvi_mean),
        "evi_mean": _r(evi_mean),
        "savi_mean": _r(savi_mean),
        "gndvi_mean": _r(gndvi_mean),
        "ndmi_mean": _r(ndmi_mean),
        "ndre_mean": _r(ndre_mean),
        "s1_vv": _r(s1_vv, 2),
        "s1_vh": _r(s1_vh, 2),
        "s1_rvi": _r(s1_rvi, 3),
        "surface_wetness_status": wetness_status,
        "phenology": phenology,
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
