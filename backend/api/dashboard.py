"""Dashboard API — aggregated field health, independent S1/S2 provenance, quality metadata, and seasonal phenology."""
from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.field import Field
from backend.models.hotspot import Hotspot
from backend.models.recommendation import Recommendation
from backend.models.satellite import IndexResult, SatelliteObservation
from backend.services.phenology_service import analyze_seasonal_phenology
from backend.services.sar_utils import (
    RVI_EXPECTED_RANGE,
    RVI_FORMULA_DESC,
    average_db_via_linear,
    classify_surface_wetness_relative,
)

router = APIRouter()


def _parse_bands_meta(obs: Optional[SatelliteObservation]) -> dict[str, Any]:
    if not obs or not obs.bands_metadata:
        return {}
    try:
        parsed = json.loads(obs.bands_metadata)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def classify_timestamp_precision(obs: Optional[SatelliteObservation]) -> tuple[str, str]:
    """Distinguish exact satellite overpass, composite window, approximate legacy migration, simulated, and unavailable."""
    if obs is None or obs.acquisition_date is None:
        return "unavailable", "No acquisition timestamp recorded for this sensor."
    if obs.is_demo:
        return "simulated", "Simulated timestamp generated in demo-simulation mode."

    meta = _parse_bands_meta(obs)
    if meta.get("timestamp_precision") == "migrated_legacy_approximate_day":
        return (
            "approximate",
            meta.get("migration_note")
            or "Approximate timestamp inherited during Phase 1 split; exact overpass time unavailable.",
        )

    comp = obs.composite_method or meta.get("composite_method")
    if comp == "10d_median_composite":
        return "composite_window", "Representative timestamp within a 10-day Sentinel-2 median composite window."

    if obs.image_id:
        return "exact", "Exact acquisition timestamp recorded from GEE scene metadata."
    return "exact", "Recorded acquisition timestamp (migrated without original scene image_id)."


def _select_provenance_bucket(
    observations: list[SatelliteObservation],
    sensor_sources: tuple[str, ...],
) -> list[SatelliteObservation]:
    """
    Never mix real satellite observations with demo-simulation records.
    If any active real observation exists for the sensor, return only real ones; otherwise return demo ones.
    """
    active = [o for o in observations if not o.is_superseded]
    real = [o for o in active if not o.is_demo and o.source in sensor_sources]
    if real:
        return real
    return [o for o in active if o.is_demo]


def compute_phenology_summary(
    optical_obs: list[SatelliteObservation],
    db: Session,
    crop_type: Optional[str] = None,
) -> dict:
    """Derive seasonal growth stage & current-cycle peak strictly from same-provenance optical history."""
    by_day = {}
    for obs in optical_obs:
        ndvi_row = (
            db.query(IndexResult)
            .filter(IndexResult.observation_id == obs.id, IndexResult.index_type == "NDVI")
            .first()
        )
        if ndvi_row and ndvi_row.mean_value is not None and obs.acquisition_date:
            day = obs.acquisition_date.strftime("%Y-%m-%d")
            if day not in by_day:
                by_day[day] = (obs.acquisition_date, float(ndvi_row.mean_value))

    points = list(by_day.values())
    return analyze_seasonal_phenology(points, crop_type=crop_type)


@router.get("/fields/{field_id}/dashboard")
def get_dashboard(field_id: int, db: Session = Depends(get_db)):
    """Return aggregated field summary separating Sentinel-2 optical, Sentinel-1 radar, quality metadata, and phenology."""
    field = db.query(Field).filter(Field.id == field_id).first()
    if not field:
        return {"error": "Field not found"}

    all_obs = (
        db.query(SatelliteObservation)
        .filter(
            SatelliteObservation.field_id == field_id,
            SatelliteObservation.status == "processed",
            SatelliteObservation.is_superseded == False,
        )
        .order_by(SatelliteObservation.acquisition_date.desc(), SatelliteObservation.id.desc())
        .all()
    )

    optical_obs_list = _select_provenance_bucket(all_obs, ("sentinel-2",))
    latest_optical = None
    optical_vals: dict[str, float] = {}
    for obs in optical_obs_list:
        rows = db.query(IndexResult).filter(IndexResult.observation_id == obs.id).all()
        if any(r.index_type.upper() == "NDVI" and r.mean_value is not None for r in rows):
            latest_optical = obs
            for r in rows:
                if r.mean_value is not None:
                    optical_vals[r.index_type.upper()] = r.mean_value
            break

    radar_obs_list = _select_provenance_bucket(all_obs, ("sentinel-1",))
    latest_radar = None
    radar_vals: dict[str, float] = {}
    for obs in radar_obs_list:
        rows = db.query(IndexResult).filter(IndexResult.observation_id == obs.id).all()
        if any(r.index_type.upper() == "S1_VV" and r.mean_value is not None for r in rows):
            latest_radar = obs
            for r in rows:
                if r.mean_value is not None:
                    radar_vals[r.index_type.upper()] = r.mean_value
            break

    hotspots = db.query(Hotspot).filter(Hotspot.field_id == field_id, Hotspot.is_active == True).all()
    stressed_hotspots = [h for h in hotspots if h.severity != "healthy"]
    critical_hotspots = [h for h in hotspots if h.severity == "severe"]

    ndvi_mean = optical_vals.get("NDVI")
    evi_mean = optical_vals.get("EVI")
    savi_mean = optical_vals.get("SAVI")
    gndvi_mean = optical_vals.get("GNDVI")
    ndmi_mean = optical_vals.get("NDMI")
    ndre_mean = optical_vals.get("NDRE")
    s1_vv = radar_vals.get("S1_VV")
    s1_vh = radar_vals.get("S1_VH")
    s1_rvi = radar_vals.get("S1_RVI")

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
    if len(optical_obs_list) >= 2:
        ndvi_values = []
        for obs in optical_obs_list[:3]:
            idx = db.query(IndexResult).filter(
                IndexResult.observation_id == obs.id, IndexResult.index_type == "NDVI"
            ).first()
            if idx and idx.mean_value is not None:
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

    phenology = compute_phenology_summary(optical_obs_list, db, crop_type=field.crop_type)

    # Radar orbit, incidence angle, and same-orbit baseline resolution
    opt_meta = _parse_bands_meta(latest_optical)
    rad_meta = _parse_bands_meta(latest_radar)
    orbit_pass = rad_meta.get("orbit_pass")
    relative_orbit = rad_meta.get("relative_orbit")
    incidence_angle_deg = rad_meta.get("incidence_angle_deg")
    delta_vv_db = rad_meta.get("delta_vv_db")
    baseline_vv_db = rad_meta.get("baseline_vv_db")
    baseline_obs_count = int(rad_meta.get("baseline_obs_count") or 0)
    orbit_consistent = bool(rad_meta.get("orbit_consistent", orbit_pass is not None or relative_orbit is not None))

    # If DB holds multiple prior same-orbit radar rows and stored metadata lacked baseline, compute in linear space
    if latest_radar and delta_vv_db is None and s1_vv is not None:
        same_orbit_prior_vv = []
        for prior in radar_obs_list:
            if prior.id == latest_radar.id:
                continue
            pm = _parse_bands_meta(prior)
            if orbit_pass is not None and pm.get("orbit_pass") != orbit_pass:
                continue
            if relative_orbit is not None and pm.get("relative_orbit") != relative_orbit:
                continue
            p_vv = db.query(IndexResult).filter(
                IndexResult.observation_id == prior.id, IndexResult.index_type == "S1_VV"
            ).first()
            if p_vv and p_vv.mean_value is not None:
                same_orbit_prior_vv.append(float(p_vv.mean_value))
        if same_orbit_prior_vv:
            baseline_vv_db = average_db_via_linear(same_orbit_prior_vv)
            baseline_obs_count = len(same_orbit_prior_vv)
            if baseline_vv_db is not None:
                delta_vv_db = round(float(s1_vv) - baseline_vv_db, 3)

    wetness_assessment = classify_surface_wetness_relative(
        s1_vv_db=s1_vv,
        delta_vv_db=delta_vv_db,
        baseline_count=baseline_obs_count,
        orbit_consistent=orbit_consistent,
        ndmi=ndmi_mean,
        ndvi=ndvi_mean,
    )

    opt_ts_prec, opt_ts_note = classify_timestamp_precision(latest_optical)
    rad_ts_prec, rad_ts_note = classify_timestamp_precision(latest_radar)

    def _r(val, n=4):
        return round(val, n) if val is not None else None

    latest_date = (
        latest_optical.acquisition_date.isoformat()
        if latest_optical and latest_optical.acquisition_date
        else (latest_radar.acquisition_date.isoformat() if latest_radar and latest_radar.acquisition_date else None)
    )

    optical_quality = {
        "available": latest_optical is not None,
        "source": latest_optical.source if latest_optical else None,
        "collection_id": latest_optical.collection_id if latest_optical else None,
        "image_id": latest_optical.image_id if latest_optical else None,
        "acquisition_date": latest_optical.acquisition_date.isoformat() if latest_optical and latest_optical.acquisition_date else None,
        "timestamp_precision": opt_ts_prec,
        "timestamp_note": opt_ts_note,
        "cloud_cover_pct": _r(latest_optical.cloud_cover_pct, 2) if latest_optical and latest_optical.cloud_cover_pct is not None else None,
        "valid_pixel_pct": (
            _r(latest_optical.valid_pixel_pct, 2)
            if latest_optical and latest_optical.valid_pixel_pct is not None
            else opt_meta.get("valid_pixel_pct")
        ),
        "observation_count": (
            latest_optical.observation_count
            if latest_optical and latest_optical.observation_count is not None
            else opt_meta.get("observation_count")
        ),
        "composite_method": (
            latest_optical.composite_method
            if latest_optical and latest_optical.composite_method
            else opt_meta.get("composite_method")
        ),
        "spatial_scale_m": opt_meta.get("scale_m", 20 if latest_optical else None),
    }

    radar_quality = {
        "available": latest_radar is not None,
        "source": latest_radar.source if latest_radar else None,
        "collection_id": latest_radar.collection_id if latest_radar else None,
        "image_id": latest_radar.image_id if latest_radar else None,
        "acquisition_date": latest_radar.acquisition_date.isoformat() if latest_radar and latest_radar.acquisition_date else None,
        "timestamp_precision": rad_ts_prec,
        "timestamp_note": rad_ts_note,
        "orbit_pass": orbit_pass,
        "relative_orbit": relative_orbit,
        "incidence_angle_deg": incidence_angle_deg,
        "baseline_vv_db": _r(baseline_vv_db, 3),
        "delta_vv_db": delta_vv_db,
        "baseline_obs_count": baseline_obs_count,
        "orbit_consistent": orbit_consistent,
        "averaging_domain": rad_meta.get("averaging_domain", "legacy_unverified" if latest_radar else None),
        "rvi_formula": rad_meta.get("rvi_formula", RVI_FORMULA_DESC if s1_rvi is not None else None),
        "rvi_expected_range": rad_meta.get("rvi_expected_range", RVI_EXPECTED_RANGE if s1_rvi is not None else None),
        "spatial_scale_m": rad_meta.get("scale_m", 10 if latest_radar else None),
        "limitation": wetness_assessment["limitation"],
    }

    scientific_provenance = {
        "measured_inputs": {
            "optical": "Sentinel-2 L2A Surface Reflectance (B2, B3, B4, B5, B8, B11 scaled / 10000; SCL + 40m cloud-edge masked)" if latest_optical else None,
            "radar": "Sentinel-1 GRD IW sigma0 (VV, VH averaged in linear power domain before dB conversion; local incidence angle)" if latest_radar else None,
        },
        "derived_indices": {
            "optical_indices": ["NDVI", "EVI", "SAVI", "GNDVI", "NDMI", "NDRE"],
            "radar_indices": {"S1_RVI": RVI_FORMULA_DESC, "expected_range": RVI_EXPECTED_RANGE},
            "note": "Spectral and radar indices are biophysical proxies, not direct laboratory chlorophyll, nitrogen, or gravimetric soil moisture measurements.",
        },
        "heuristic_interpretations": {
            "overall_health_label": overall_health,
            "surface_wetness_status": wetness_assessment["status"],
            "phenology_stage": phenology.get("stage"),
            "phenology_stage_confidence": phenology.get("stage_confidence"),
            "crop_calendar_is_proof": False,
        },
    }

    return {
        "field_name": field.name,
        "crop_type": field.crop_type,
        "growth_stage": field.growth_stage,
        "area_ha": field.area_ha,
        "latest_observation_date": latest_date,
        "optical_timestamp_precision": opt_ts_prec,
        "radar_observation_date": latest_radar.acquisition_date.isoformat() if latest_radar and latest_radar.acquisition_date else None,
        "radar_timestamp_precision": rad_ts_prec,
        "is_demo": bool(latest_optical.is_demo) if latest_optical else (bool(latest_radar.is_demo) if latest_radar else None),
        "optical_source": latest_optical.source if latest_optical else None,
        "radar_source": latest_radar.source if latest_radar else None,
        "optical_quality": optical_quality,
        "radar_quality": radar_quality,
        "radar_wetness_assessment": wetness_assessment,
        "scientific_provenance": scientific_provenance,
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
        "surface_wetness_status": wetness_assessment["status"],
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
