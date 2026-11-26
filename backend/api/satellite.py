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


def _upsert_observation(
    field_id: int,
    source: str,
    acq_date: datetime,
    collection_id: str | None,
    image_id: str | None,
    cloud_cover_pct: float | None,
    bands_metadata: dict | None,
    is_demo: bool,
    db: Session,
    overwrite_indices: bool = True,
    valid_pixel_pct: float | None = None,
    observation_count: int | None = None,
    composite_method: str | None = None,
) -> tuple[SatelliteObservation, bool]:
    """
    Idempotently upsert one active SatelliteObservation per (field_id, source, acquisition_day).
    Returns (observation, should_write_indices).
    """
    acq_day = acq_date.strftime("%Y-%m-%d")
    existing = (
        db.query(SatelliteObservation)
        .filter(
            SatelliteObservation.field_id == field_id,
            SatelliteObservation.source == source,
            SatelliteObservation.acquisition_day == acq_day,
            SatelliteObservation.is_superseded == False,
        )
        .first()
    )

    meta_json = json.dumps(bands_metadata) if bands_metadata is not None else None

    if existing:
        if not overwrite_indices:
            return existing, False
        db.query(IndexResult).filter(IndexResult.observation_id == existing.id).delete()
        existing.acquisition_date = acq_date
        existing.collection_id = collection_id
        existing.image_id = image_id
        existing.cloud_cover_pct = cloud_cover_pct
        existing.valid_pixel_pct = valid_pixel_pct
        existing.observation_count = observation_count
        existing.composite_method = composite_method
        existing.bands_metadata = meta_json
        existing.is_demo = is_demo
        existing.status = "processed"
        existing.processed_at = datetime.utcnow()
        db.commit()
        return existing, True

    obs_record = SatelliteObservation(
        field_id=field_id,
        source=source,
        collection_id=collection_id,
        image_id=image_id,
        acquisition_date=acq_date,
        acquisition_day=acq_day,
        cloud_cover_pct=cloud_cover_pct,
        valid_pixel_pct=valid_pixel_pct,
        observation_count=observation_count,
        composite_method=composite_method,
        bands_metadata=meta_json,
        status="processed",
        is_demo=is_demo,
        is_superseded=False,
        processed_at=datetime.utcnow(),
    )
    db.add(obs_record)
    db.commit()
    db.refresh(obs_record)
    return obs_record, True


def _detect_and_store_hotspots(
    field: Field,
    obs: SatelliteObservation,
    results: dict,
    cells: list,
    db: Session,
) -> list[Hotspot]:
    """
    Score per-zone satellite measurements and archive prior hotspots rather than deleting them.
    """
    if not cells or not results.get("optical_available", True):
        return []

    ndvi_stats = results.get("ndvi_stats")
    if not ndvi_stats or ndvi_stats.get("NDVI_mean") is None:
        return []

    try:
        field_geom = shape(json.loads(field.boundary_geojson))
    except Exception:
        return []

    ndvi_mean = float(ndvi_stats["NDVI_mean"])
    ndmi_stats = results.get("ndmi_stats") or {}
    ndre_stats = results.get("ndre_stats") or {}
    ndmi_mean = float(ndmi_stats["NDMI_mean"]) if ndmi_stats.get("NDMI_mean") is not None else None
    ndre_mean = float(ndre_stats["NDRE_mean"]) if ndre_stats.get("NDRE_mean") is not None else None

    zone_stats = results.get("zone_stats", {})
    is_demo = bool(results.get("is_demo", False))

    valid_cells = []
    features = []
    ndvi_vals, ndmi_vals, ndre_vals = [], [], []

    for idx, geom in enumerate(cells):
        z = zone_stats.get(idx)
        if not z or z.get("NDVI") is None:
            continue
        c_ndvi = float(z["NDVI"])
        c_ndmi = float(z["NDMI"]) if z.get("NDMI") is not None else None
        c_ndre = float(z["NDRE"]) if z.get("NDRE") is not None else None

        # Only supply measured values to DB; use field mean temporarily in feature vector if a 20m band pixel was None
        eff_ndmi = c_ndmi if c_ndmi is not None else (ndmi_mean if ndmi_mean is not None else 0.0)
        eff_ndre = c_ndre if c_ndre is not None else (ndre_mean if ndre_mean is not None else 0.0)

        valid_cells.append((geom, c_ndvi, c_ndmi, c_ndre))
        ndvi_vals.append(c_ndvi)
        ndmi_vals.append(eff_ndmi)
        ndre_vals.append(eff_ndre)
        features.append([
            c_ndvi,
            eff_ndmi,
            eff_ndre,
            c_ndvi - ndvi_mean,
            eff_ndmi - (ndmi_mean if ndmi_mean is not None else eff_ndmi),
        ])

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

    # Archive previous active hotspots for this field instead of deleting historical records
    db.query(Hotspot).filter(
        Hotspot.field_id == field.id,
        Hotspot.is_active == True,
    ).update({"is_active": False}, synchronize_session=False)
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
        ndmi_dev = round(c_ndmi - ndmi_mean, 4) if (c_ndmi is not None and ndmi_mean is not None) else None
        ndre_dev = round(c_ndre - ndre_mean, 4) if (c_ndre is not None and ndre_mean is not None) else None

        if severity == "healthy" and not is_ml_anomaly:
            issue = "Healthy Vegetation"
        elif (ndmi_dev is not None and ndmi_dev < -0.08) or (c_ndmi is not None and c_ndmi < 0.0):
            issue = "Moisture Stress"
        elif (ndre_dev is not None and ndre_dev < -0.06) or (c_ndre is not None and c_ndre < 0.25):
            issue = "Chlorophyll / Nitrogen Stress"
        else:
            issue = "Low Canopy Vigor"

        method = "isolation_forest" if is_ml_anomaly else "baseline_heuristic"
        ndmi_txt = f"{c_ndmi:.2f}" if c_ndmi is not None else "N/A"
        ndre_txt = f"{c_ndre:.2f}" if c_ndre is not None else "N/A"
        explanation = (
            f"{source_tag} ({method.replace('_', ' ')}): "
            f"NDVI {c_ndvi:.2f} ({ndvi_dev:+.2f}), NDMI {ndmi_txt}, NDRE {ndre_txt}."
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
            ndmi_value=round(c_ndmi, 4) if c_ndmi is not None else None,
            ndre_value=round(c_ndre, 4) if c_ndre is not None else None,
            ndvi_deviation=ndvi_dev,
            ndmi_deviation=ndmi_dev,
            ndre_deviation=ndre_dev,
            likely_issue=issue,
            explanation=explanation,
            detection_method=method,
            persistence_count=1,
            first_detected=obs.acquisition_date or datetime.utcnow(),
            is_active=True,
        )
        db.add(hs)
        created.append(hs)

    db.commit()
    return created


def _store_time_series(field_id: int, time_series: list[dict], is_demo: bool, db: Session):
    """Persist historical Sentinel-2 dates/composites idempotently with full quality provenance."""
    if not time_series:
        return

    for pt in time_series:
        dt = pt["acquisition_date"]
        source = pt.get("source") or ("demo-simulation" if is_demo else "sentinel-2")
        obs_count = pt.get("observation_count", 1)
        valid_pct = pt.get("valid_pixel_pct")
        comp_method = pt.get("composite_method") or ("demo_simulated" if is_demo else "single_scene")
        meta_payload = {
            "scale_m": 20,
            "origin": "time_series_180d_composite",
            "is_demo": is_demo,
            "valid_pixel_pct": valid_pct,
            "observation_count": obs_count,
            "composite_method": comp_method,
            "composite_period_start": pt.get("composite_period_start"),
            "composite_period_end": pt.get("composite_period_end"),
            "contributing_image_ids": pt.get("contributing_image_ids", []),
        }
        hist_obs, should_write = _upsert_observation(
            field_id=field_id,
            source=source,
            acq_date=dt,
            collection_id=pt.get("collection_id"),
            image_id=pt.get("image_id"),
            cloud_cover_pct=pt.get("cloud_cover"),
            bands_metadata=meta_payload,
            is_demo=is_demo,
            db=db,
            overwrite_indices=False,  # preserve existing higher-detail observations intact
            valid_pixel_pct=valid_pct,
            observation_count=obs_count,
            composite_method=comp_method,
        )
        if not should_write:
            continue

        for idx_name in ["NDVI", "EVI", "SAVI", "GNDVI", "NDMI", "NDRE"]:
            val = pt.get(idx_name)
            if val is None:
                continue
            fval = float(val)
            db.add(
                IndexResult(
                    observation_id=hist_obs.id,
                    index_type=idx_name,
                    mean_value=fval,
                    min_value=None,
                    max_value=None,
                    std_value=None,
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

    is_demo = bool(results.get("is_demo", False))
    optical_available = bool(results.get("optical_available", True))
    radar_available = bool(results.get("radar_available", False))

    primary_obs = None
    optical_obs = None
    radar_obs = None

    # 1. Persist Optical Observation (Sentinel-2 or Demo) ONLY when optical data exists
    if optical_available:
        opt_source = "demo-simulation" if is_demo else "sentinel-2"
        optical_obs, _ = _upsert_observation(
            field_id=field_id,
            source=opt_source,
            acq_date=results["acquisition_date"],
            collection_id=results.get("collection_id"),
            image_id=results.get("image_id"),
            cloud_cover_pct=results.get("cloud_cover"),
            bands_metadata=results.get("bands_metadata"),
            is_demo=is_demo,
            db=db,
            overwrite_indices=True,
            valid_pixel_pct=results.get("valid_pixel_pct"),
            observation_count=results.get("observation_count", 1),
            composite_method=results.get("composite_method"),
        )

        optical_pairs = [
            ("NDVI", results.get("ndvi_stats")),
            ("EVI", results.get("evi_stats")),
            ("SAVI", results.get("savi_stats")),
            ("GNDVI", results.get("gndvi_stats")),
            ("NDMI", results.get("ndmi_stats")),
            ("NDRE", results.get("ndre_stats")),
        ]
        for idx_name, stats in optical_pairs:
            if not stats or stats.get(f"{idx_name}_mean") is None:
                continue
            db.add(
                IndexResult(
                    observation_id=optical_obs.id,
                    index_type=idx_name,
                    mean_value=stats[f"{idx_name}_mean"],
                    min_value=stats.get(f"{idx_name}_min"),
                    max_value=stats.get(f"{idx_name}_max"),
                    std_value=stats.get(f"{idx_name}_stdDev"),
                )
            )
        db.commit()
        primary_obs = optical_obs

    # 2. Persist Sentinel-1 SAR Observation independently with its own acquisition timestamp & provenance
    s1_stats = results.get("s1_stats")
    if radar_available and s1_stats:
        s1_source = "demo-simulation" if is_demo else "sentinel-1"
        s1_meta = {
            "orbit_pass": s1_stats.get("orbit_pass"),
            "relative_orbit": s1_stats.get("relative_orbit"),
            "incidence_angle_deg": s1_stats.get("incidence_angle_deg"),
            "vv_linear_mean": s1_stats.get("vv_linear_mean"),
            "vh_linear_mean": s1_stats.get("vh_linear_mean"),
            "baseline_vv_db": s1_stats.get("baseline_vv_db"),
            "baseline_vh_db": s1_stats.get("baseline_vh_db"),
            "delta_vv_db": s1_stats.get("delta_vv_db"),
            "baseline_obs_count": s1_stats.get("baseline_obs_count", 0),
            "orbit_consistent": s1_stats.get("orbit_consistent", True),
            "rvi_formula": s1_stats.get("rvi_formula"),
            "rvi_expected_range": s1_stats.get("rvi_expected_range"),
            "averaging_domain": s1_stats.get("averaging_domain", "linear_power_before_db"),
            "scale_m": s1_stats.get("spatial_scale_m", 10),
            "is_demo": is_demo,
        }
        radar_obs, _ = _upsert_observation(
            field_id=field_id,
            source=s1_source,
            acq_date=s1_stats["acquisition_date"],
            collection_id=s1_stats.get("collection_id"),
            image_id=s1_stats.get("image_id"),
            cloud_cover_pct=None,  # Radar does not have optical cloud cover
            bands_metadata=s1_meta,
            is_demo=is_demo,
            db=db,
            overwrite_indices=True,
            valid_pixel_pct=None,
            observation_count=1,
            composite_method="single_orbit_pass",
        )
        for s1_key in ["S1_VV", "S1_VH", "S1_RVI"]:
            val = s1_stats.get(s1_key)
            if val is None:
                continue
            db.add(
                IndexResult(
                    observation_id=radar_obs.id,
                    index_type=s1_key,
                    mean_value=float(val),
                    min_value=None,
                    max_value=None,
                    std_value=None,
                )
            )
        db.commit()
        if primary_obs is None:
            primary_obs = radar_obs

    # 3. Store historical Sentinel-2 time series without overwriting existing observations
    _store_time_series(field_id, results.get("time_series", []), is_demo, db)

    zones = _detect_and_store_hotspots(field, optical_obs or primary_obs, results, cells, db)
    recs = generate_and_store_recommendations(field_id, db)

    stressed_count = sum(1 for z in zones if z.severity != "healthy")
    return {
        "message": "Analysis complete",
        "observation_id": primary_obs.id if primary_obs else None,
        "optical_observation_id": optical_obs.id if optical_obs else None,
        "radar_observation_id": radar_obs.id if radar_obs else None,
        "grid_size": f"{grid_n}x{grid_n}",
        "zones_measured": len(zones),
        "hotspots_detected": stressed_count,
        "optical_available": optical_available,
        "radar_available": radar_available,
        "time_series_points": len(results.get("time_series", [])),
        "time_series_gaps": len(results.get("time_series_gaps", [])),
        "time_series_meta": results.get("time_series_meta"),
        "is_demo": is_demo,
        "recommendations_generated": len(recs),
    }


@router.get("/observations/{id}/tiles/{index_type}/{z}/{x}/{y}.png")
def get_tile(id: int, index_type: str, z: int, x: int, y: int):
    raise HTTPException(status_code=404, detail="Tile proxy not fully implemented")
