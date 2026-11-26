from __future__ import annotations

import json
from datetime import datetime
import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from shapely.geometry import box, mapping, shape
from sqlalchemy.orm import Session

from backend.api.recommendations import generate_and_store_recommendations
from backend.database import get_db
from backend.ml.anomaly_detector import IsolationForestDetector
from backend.models.field import Field
from backend.models.hotspot import Hotspot
from backend.models.satellite import IndexResult, SatelliteObservation
from backend.services.gee_service import get_gee_service
from backend.services.hotspot_service import HotspotService
from backend.utils.geo import calculate_area_ha

router = APIRouter()


def _build_adaptive_grid(field: Field):
    """
    Build sub-field grid cells scaled to Sentinel-2's physical 10m-20m pixel resolution:
    - < 0.25 ha (tiny plot): 1 whole-field zone (never fake sub-pixel boxes)
    - 0.25 - 1.0 ha: 2x2 grid (up to 4 zones)
    - >= 1.0 ha: 4x4 grid (up to 16 zones)
    """
    try:
        field_geom = shape(json.loads(field.boundary_geojson))
    except Exception:
        return [], [], 0

    area_ha = field.area_ha or calculate_area_ha(field.boundary_geojson)
    if area_ha < 0.25:
        grid_n = 1
    elif area_ha < 1.0:
        grid_n = 2
    else:
        grid_n = 4

    if grid_n == 1:
        geom = field_geom if field_geom.geom_type == "Polygon" else field_geom.convex_hull
        return [geom], [mapping(geom)], 1

    minx, miny, maxx, maxy = field_geom.bounds
    dx = (maxx - minx) / grid_n
    dy = (maxy - miny) / grid_n
    if dx <= 0 or dy <= 0:
        return [], [], 0

    cells = []
    zone_geoms = []
    for i in range(grid_n):
        for j in range(grid_n):
            cell = box(minx + i * dx, miny + j * dy, minx + (i + 1) * dx, miny + (j + 1) * dy)
            inter = field_geom.intersection(cell)
            if inter.is_empty or inter.area <= 0:
                continue
            if inter.geom_type != "Polygon":
                inter = inter.convex_hull
            if inter.geom_type != "Polygon" or inter.area <= 0:
                continue
            cells.append(inter)
            zone_geoms.append(mapping(inter))

    return cells, zone_geoms, grid_n


def _detect_and_store_hotspots(
    field: Field,
    obs: SatelliteObservation,
    results: dict,
    cells: list,
    db: Session,
) -> list[Hotspot]:
    """Score real per-zone satellite measurements and run Isolation Forest anomaly detection."""
    if not cells:
        return []

    try:
        field_geom = shape(json.loads(field.boundary_geojson))
    except Exception:
        return []

    ndvi_mean = float(results["ndvi_stats"].get("NDVI_mean", 0.5))
    ndmi_mean = float(results["ndmi_stats"].get("NDMI_mean", 0.1))
    ndre_mean = float(results["ndre_stats"].get("NDRE_mean", 0.3))
    zone_stats = results.get("zone_stats", {})
    is_demo = bool(results.get("is_demo", False))

    valid_cells = []
    features = []
    ndvi_vals, ndmi_vals, ndre_vals = [], [], []

    for idx, geom in enumerate(cells):
        z = zone_stats.get(idx)
        if not z:
            continue
        c_ndvi = float(z["NDVI"])
        c_ndmi = float(z["NDMI"])
        c_ndre = float(z["NDRE"])
        valid_cells.append((geom, c_ndvi, c_ndmi, c_ndre))
        ndvi_vals.append(c_ndvi)
        ndmi_vals.append(c_ndmi)
        ndre_vals.append(c_ndre)
        features.append([c_ndvi, c_ndmi, c_ndre, c_ndvi - ndvi_mean, c_ndmi - ndmi_mean])

    if not valid_cells:
        return []

    hs_service = HotspotService()
    scores = hs_service.detect_hotspots_baseline(
        np.array(ndvi_vals), np.array(ndmi_vals), np.array(ndre_vals)
    )

    ml_preds = np.ones(len(features))
    if len(features) >= 4:
        detector = IsolationForestDetector(contamination=0.2, random_state=42)
        detector.fit(np.array(features))
        ml_preds = detector.predict(np.array(features))

    db.query(Hotspot).filter(Hotspot.field_id == field.id).delete()
    db.commit()

    created = []
    field_area = field.area_ha or 10.0
    total_poly_area = max(field_geom.area, 1e-12)
    source_tag = "Demo Simulation" if is_demo else "Sentinel-2 L2A real pixels"

    for idx, (geom, c_ndvi, c_ndmi, c_ndre) in enumerate(valid_cells):
        score = float(scores[idx])
        is_ml_anomaly = int(ml_preds[idx]) == -1

        if score >= 80:
            severity = "healthy"
        elif score >= 60:
            severity = "mild"
        elif score >= 40:
            severity = "moderate"
        else:
            severity = "severe"

        ndvi_dev = round(c_ndvi - ndvi_mean, 4)
        ndmi_dev = round(c_ndmi - ndmi_mean, 4)
        ndre_dev = round(c_ndre - ndre_mean, 4)

        if severity == "healthy" and not is_ml_anomaly:
            issue = "Healthy Vegetation"
        elif ndmi_dev < -0.08 or c_ndmi < 0.0:
            issue = "Moisture Stress"
        elif ndre_dev < -0.06 or c_ndre < 0.25:
            issue = "Chlorophyll / Nitrogen Stress"
        else:
            issue = "Low Canopy Vigor"

        method = "isolation_forest" if is_ml_anomaly else "baseline_heuristic"
        explanation = (
            f"{source_tag} ({method.replace('_', ' ')}): "
            f"NDVI {c_ndvi:.2f} ({ndvi_dev:+.2f}), NDMI {c_ndmi:.2f} ({ndmi_dev:+.2f}), NDRE {c_ndre:.2f} ({ndre_dev:+.2f})."
        )

        centroid = geom.centroid
        cell_ha = round(field_area * (geom.area / total_poly_area), 2)

        hs = Hotspot(
            field_id=field.id,
            observation_id=obs.id,
            geometry_geojson=json.dumps(mapping(geom)),
            center_lat=round(centroid.y, 6),
            center_lng=round(centroid.x, 6),
            area_ha=max(0.01, cell_ha),
            severity=severity,
            health_score=round(score, 1),
            ndvi_value=round(c_ndvi, 4),
            ndmi_value=round(c_ndmi, 4),
            ndre_value=round(c_ndre, 4),
            ndvi_deviation=ndvi_dev,
            ndmi_deviation=ndmi_dev,
            ndre_deviation=ndre_dev,
            likely_issue=issue,
            explanation=explanation,
            detection_method=method,
            persistence_count=1,
            first_detected=obs.acquisition_date or datetime.utcnow(),
        )
        db.add(hs)
        created.append(hs)

    db.commit()
    return created


def _store_time_series(field_id: int, time_series: list[dict], latest_obs_date: datetime, db: Session):
    """Persist historical Sentinel-2 time-series points without duplicating existing dates."""
    if not time_series:
        return
    existing = db.query(SatelliteObservation).filter(SatelliteObservation.field_id == field_id).all()
    existing_days = {
        o.acquisition_date.strftime("%Y-%m-%d")
        for o in existing
        if o.acquisition_date
    }
    latest_day = latest_obs_date.strftime("%Y-%m-%d") if latest_obs_date else None

    for pt in time_series:
        dt = pt["acquisition_date"]
        day = dt.strftime("%Y-%m-%d")
        if day == latest_day or day in existing_days:
            continue
        existing_days.add(day)
        hist_obs = SatelliteObservation(
            field_id=field_id,
            acquisition_date=dt,
            cloud_cover_pct=pt.get("cloud_cover", 0.0),
            status="processed",
            processed_at=datetime.utcnow(),
        )
        db.add(hist_obs)
        db.flush()
        for idx_name in ["NDVI", "EVI", "SAVI", "GNDVI", "NDMI", "NDRE"]:
            val = float(pt.get(idx_name, 0.0))
            db.add(
                IndexResult(
                    observation_id=hist_obs.id,
                    index_type=idx_name,
                    mean_value=val,
                    min_value=val,
                    max_value=val,
                    std_value=0.0,
                )
            )
    db.commit()


@router.post("/fields/{field_id}/analyze")
def analyze_field(
    field_id: int,
    start_date: str = "2023-01-01",
    end_date: str = "2026-12-31",
    cloud_max: int = 20,
    db: Session = Depends(get_db),
):
    field = db.query(Field).filter(Field.id == field_id).first()
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")

    gee = get_gee_service()
    if not gee.initialize():
        raise HTTPException(status_code=500, detail="GEE Initialization failed")

    cells, zone_geoms, grid_n = _build_adaptive_grid(field)
    results = gee.analyze_field(
        field.boundary_geojson,
        start_date,
        end_date,
        cloud_max,
        zone_geoms=zone_geoms,
    )
    if not results:
        raise HTTPException(status_code=404, detail="No valid satellite data found in date range")

    acq_date = results["acquisition_date"]

    # Upsert if the exact same acquisition day already exists so repeated clicks stay clean
    day_prefix = acq_date.strftime("%Y-%m-%d")
    obs = (
        db.query(SatelliteObservation)
        .filter(SatelliteObservation.field_id == field_id)
        .order_by(SatelliteObservation.id.desc())
        .all()
    )
    existing_same_day = next(
        (o for o in obs if o.acquisition_date and o.acquisition_date.strftime("%Y-%m-%d") == day_prefix),
        None,
    )

    if existing_same_day:
        db.query(IndexResult).filter(IndexResult.observation_id == existing_same_day.id).delete()
        existing_same_day.cloud_cover_pct = results["cloud_cover"]
        existing_same_day.processed_at = datetime.utcnow()
        obs_record = existing_same_day
        db.commit()
    else:
        obs_record = SatelliteObservation(
            field_id=field_id,
            acquisition_date=acq_date,
            cloud_cover_pct=results["cloud_cover"],
            status="processed",
            processed_at=datetime.utcnow(),
        )
        db.add(obs_record)
        db.commit()
        db.refresh(obs_record)

    optical_pairs = [
        ("NDVI", results["ndvi_stats"]),
        ("EVI", results["evi_stats"]),
        ("SAVI", results["savi_stats"]),
        ("GNDVI", results["gndvi_stats"]),
        ("NDMI", results["ndmi_stats"]),
        ("NDRE", results["ndre_stats"]),
    ]
    for idx_name, stats in optical_pairs:
        db.add(
            IndexResult(
                observation_id=obs_record.id,
                index_type=idx_name,
                mean_value=stats[f"{idx_name}_mean"],
                min_value=stats[f"{idx_name}_min"],
                max_value=stats[f"{idx_name}_max"],
                std_value=stats[f"{idx_name}_stdDev"],
            )
        )

    s1_stats = results.get("s1_stats")
    if s1_stats:
        for s1_key in ["S1_VV", "S1_VH", "S1_RVI"]:
            val = float(s1_stats.get(s1_key, 0.0))
            db.add(
                IndexResult(
                    observation_id=obs_record.id,
                    index_type=s1_key,
                    mean_value=val,
                    min_value=val,
                    max_value=val,
                    std_value=0.0,
                )
            )
    db.commit()

    # Save historical Sentinel-2 time series for phenology/growth curve
    _store_time_series(field_id, results.get("time_series", []), acq_date, db)

    zones = _detect_and_store_hotspots(field, obs_record, results, cells, db)
    recs = generate_and_store_recommendations(field_id, db)

    stressed_count = sum(1 for z in zones if z.severity != "healthy")
    return {
        "message": "Analysis complete",
        "observation_id": obs_record.id,
        "grid_size": f"{grid_n}x{grid_n}",
        "zones_measured": len(zones),
        "hotspots_detected": stressed_count,
        "optical_available": results.get("optical_available", True),
        "radar_available": results.get("radar_available", False),
        "time_series_points": len(results.get("time_series", [])),
        "is_demo": bool(results.get("is_demo", False)),
        "recommendations_generated": len(recs),
    }


@router.get("/observations/{id}/tiles/{index_type}/{z}/{x}/{y}.png")
def get_tile(id: int, index_type: str, z: int, x: int, y: int):
    raise HTTPException(status_code=404, detail="Tile proxy not fully implemented")
