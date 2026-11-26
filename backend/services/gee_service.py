"""
Google Earth Engine (GEE) & Demo processing service for Sentinel-2 (optical) and Sentinel-1 (SAR).

Phase 2 Scientific Standards:
- Sentinel-2 L2A (COPERNICUS/S2_SR_HARMONIZED):
  * Full SCL masking: 0 (no data), 1 (saturated/defective), 3 (cloud shadow),
    8 (cloud medium), 9 (cloud high), 10 (thin cirrus), 11 (snow/ice).
  * Morphological cloud-edge dilation mask (40 m around SCL cloud classes 8/9/10).
  * Relaxed tile-level cloud pre-filter (max(cloud_max, 65%)) paired with field-geometry
    clear-pixel percentage calculation.
  * Standardized 20 m spatial scale across whole-field statistics and historical composites.
  * Same-day overlapping MGRS scenes mosaicked via masked median across field geometry.
  * Missing/masked pixels remain masked (never unmasked to 0.0).
  * 180-day historical window binned into ~10-day composites retaining missing observation gaps.
- Sentinel-1 GRD IW (COPERNICUS/S1_GRD):
  * Pixel-wise dB -> linear power conversion BEFORE spatial averaging.
  * Averaged linear power converted back to dB for presentation.
  * Dual-pol RVI computed from spatially averaged linear power: 4 * VH_lin / (VV_lin + VH_lin).
  * Same-orbit (orbitProperties_pass + relativeOrbitNumber_start) filtering for temporal change.
  * Incidence angle ('angle' band) captured and persisted in metadata.
"""
from __future__ import annotations

import logging
import random
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Any, Optional

import ee
import numpy as np

from backend.config import settings
from backend.services.sar_utils import (
    RVI_EXPECTED_RANGE,
    RVI_FORMULA_DESC,
    average_db_via_linear,
    compute_dual_pol_rvi,
    linear_to_db,
    select_consistent_orbit_group,
)

logger = logging.getLogger(__name__)

OPTICAL_BANDS = ["NDVI", "EVI", "SAVI", "GNDVI", "NDMI", "NDRE"]
S2_COLLECTION = "COPERNICUS/S2_SR_HARMONIZED"
S1_COLLECTION = "COPERNICUS/S1_GRD"

# Standardized spatial processing scales
STANDARD_S2_SCALE_M = 20
STANDARD_S1_SCALE_M = 10

# SCL classes excluded from valid agricultural reflectance:
# 0: NO_DATA, 1: SATURATED_OR_DEFECTIVE, 3: CLOUD_SHADOWS,
# 8: CLOUD_MEDIUM_PROBABILITY, 9: CLOUD_HIGH_PROBABILITY, 10: THIN_CIRRUS, 11: SNOW_ICE
S2_MASKED_SCL_CLASSES = (0, 1, 3, 8, 9, 10, 11)
S2_CLOUD_EDGE_RADIUS_M = 40
S2_TILE_CLOUD_PREFILTER_MAX = 65
S2_MIN_FIELD_CLEAR_PCT = 50.0
S2_TIME_SERIES_WINDOW_DAYS = 180
S2_COMPOSITE_BIN_DAYS = 10


def compute_scl_clear_mask_array(scl_values: np.ndarray) -> np.ndarray:
    """Pure-NumPy equivalent of SCL class validity check for unit validation (no zero-fill)."""
    arr = np.asarray(scl_values)
    clear = np.ones(arr.shape, dtype=bool)
    for cls in S2_MASKED_SCL_CLASSES:
        clear &= (arr != cls)
    return clear


def group_same_day_scenes(scenes: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Group candidate scenes by canonical YYYY-MM-DD acquisition day."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for s in scenes:
        dt = s.get("acquisition_date")
        if dt is None:
            continue
        day = dt.strftime("%Y-%m-%d")
        grouped.setdefault(day, []).append(s)
    return grouped


def build_10day_composite_bins(
    window_start: datetime,
    window_end: datetime,
    step_days: int = S2_COMPOSITE_BIN_DAYS,
) -> list[tuple[datetime, datetime]]:
    """Build contiguous non-overlapping ~10-day bins covering [window_start, window_end]."""
    bins: list[tuple[datetime, datetime]] = []
    cur = window_start
    while cur <= window_end:
        bin_end = min(window_end + timedelta(seconds=1), cur + timedelta(days=step_days))
        bins.append((cur, bin_end))
        cur = cur + timedelta(days=step_days)
    return bins


class GEEService:
    def __init__(self):
        self._initialized = False

    def initialize(self):
        """Initialize GEE. Uses service account JSON or key file if configured, else OAuth."""
        if self._initialized:
            return True
        try:
            if settings.GEE_SERVICE_ACCOUNT_JSON:
                credentials = ee.ServiceAccountCredentials(
                    email=None,
                    key_data=settings.GEE_SERVICE_ACCOUNT_JSON,
                )
                if settings.GEE_PROJECT_ID:
                    ee.Initialize(credentials, project=settings.GEE_PROJECT_ID)
                else:
                    ee.Initialize(credentials)
            elif settings.GEE_SERVICE_ACCOUNT_KEY_PATH:
                credentials = ee.ServiceAccountCredentials(
                    email=None,
                    key_file=settings.GEE_SERVICE_ACCOUNT_KEY_PATH,
                )
                if settings.GEE_PROJECT_ID:
                    ee.Initialize(credentials, project=settings.GEE_PROJECT_ID)
                else:
                    ee.Initialize(credentials)
            elif settings.GEE_PROJECT_ID:
                ee.Initialize(project=settings.GEE_PROJECT_ID)
            else:
                ee.Initialize()
            self._initialized = True
            logger.info("GEE initialized successfully")
            return True
        except Exception as e:
            logger.error(f"GEE initialization failed: {e}")
            return False

    def get_sentinel2_collection(self, geometry, start_date, end_date, cloud_max=20):
        """
        Query Sentinel-2 SR Harmonized collection using a relaxed tile-level cloud filter
        so small clear fields inside partly cloudy 110 km MGRS tiles are not discarded prematurely.
        Field-level clear-pixel filtering is applied after SCL + cloud-edge masking.
        """
        tile_cloud_limit = max(int(cloud_max), S2_TILE_CLOUD_PREFILTER_MAX)
        return (
            ee.ImageCollection(S2_COLLECTION)
            .filterBounds(geometry)
            .filterDate(start_date, end_date)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", tile_cloud_limit))
        )

    def mask_clouds(self, image):
        """
        Apply Sentinel-2 SCL validity + cloud/shadow/snow + morphological cloud-edge mask
        and scale optical reflectance bands to [0, 1] surface reflectance.
        Never unmasks missing pixels to zero; attaches CLEAR_MASK [0|1] solely for valid-pixel accounting.
        """
        scl = image.select("SCL")
        valid_scl = (
            scl.neq(0)
            .And(scl.neq(1))
            .And(scl.neq(3))
            .And(scl.neq(8))
            .And(scl.neq(9))
            .And(scl.neq(10))
            .And(scl.neq(11))
        )
        # Morphological 40 m dilation around cloud core pixels (SCL 8, 9, 10) catches thin cloud edges
        cloud_core = scl.eq(8).Or(scl.eq(9)).Or(scl.eq(10))
        cloud_edge_buffer = cloud_core.focalMax(radius=S2_CLOUD_EDGE_RADIUS_M, units="meters")
        mask = valid_scl.And(cloud_edge_buffer.Not())

        # Reflectance bands keep missing pixels masked (nodata); CLEAR_MASK tracks fraction of clear pixels
        clear_band = mask.updateMask(scl.gte(0)).toFloat().rename("CLEAR_MASK")
        scaled_optical = (
            image.select(["B2", "B3", "B4", "B5", "B8", "B11"])
            .updateMask(mask)
            .divide(10000.0)
        )
        return ee.Image(
            scaled_optical.addBands(clear_band).copyProperties(
                image, ["system:time_start", "system:index", "CLOUDY_PIXEL_PERCENTAGE"]
            )
        )

    def calculate_indices(self, image):
        """
        Calculate NDVI, EVI, SAVI, GNDVI, NDMI, and NDRE from scaled Sentinel-2 reflectance.
        Masks out non-finite or zero-denominator pixels rather than converting to zero.
        """
        ndvi = image.normalizedDifference(["B8", "B4"]).rename("NDVI")
        ndmi = image.normalizedDifference(["B8", "B11"]).rename("NDMI")
        ndre = image.normalizedDifference(["B8", "B5"]).rename("NDRE")
        gndvi = image.normalizedDifference(["B8", "B3"]).rename("GNDVI")

        savi_denom = image.expression("NIR + RED + 0.5", {"NIR": image.select("B8"), "RED": image.select("B4")})
        savi = (
            image.expression(
                "1.5 * (NIR - RED) / (NIR + RED + 0.5)",
                {"NIR": image.select("B8"), "RED": image.select("B4")},
            )
            .updateMask(savi_denom.neq(0))
            .clamp(-1, 1.5)
            .rename("SAVI")
        )

        evi_denom = image.expression(
            "NIR + 6 * RED - 7.5 * BLUE + 1",
            {"NIR": image.select("B8"), "RED": image.select("B4"), "BLUE": image.select("B2")},
        )
        evi = (
            image.expression(
                "2.5 * (NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1)",
                {"NIR": image.select("B8"), "RED": image.select("B4"), "BLUE": image.select("B2")},
            )
            .updateMask(evi_denom.abs().gt(1e-6))
            .clamp(-1, 1.5)
            .rename("EVI")
        )
        return image.addBands([ndvi, evi, savi, gndvi, ndmi, ndre])

    def _get_sentinel1_stats(self, ee_geom, end_date: str) -> Optional[dict[str, Any]]:
        """
        Fetch Sentinel-1 SAR GRD IW scenes, convert VV/VH dB -> linear power BEFORE spatial averaging,
        convert averaged linear power back to dB, compute dual-pol RVI from averaged linear inputs,
        filter temporal baseline to consistent orbit_pass + relative_orbit, and capture incidence angle.
        """
        try:
            end_dt = datetime.strptime(end_date[:10], "%Y-%m-%d")
        except Exception:
            end_dt = datetime.utcnow()
        start_s1 = (end_dt - timedelta(days=120)).strftime("%Y-%m-%d")
        end_s1 = (end_dt + timedelta(days=1)).strftime("%Y-%m-%d")

        try:
            s1_col = (
                ee.ImageCollection(S1_COLLECTION)
                .filterBounds(ee_geom)
                .filterDate(start_s1, end_s1)
                .filter(ee.Filter.eq("instrumentMode", "IW"))
                .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
                .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
                .sort("system:time_start", False)
                .limit(20)
            )

            def _per_s1_image(img):
                vv_lin = ee.Image(10).pow(img.select("VV").divide(10.0)).rename("VV_lin")
                vh_lin = ee.Image(10).pow(img.select("VH").divide(10.0)).rename("VH_lin")
                angle = img.select("angle").rename("angle")
                lin_stack = vv_lin.addBands(vh_lin).addBands(angle)
                vals = lin_stack.reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=ee_geom,
                    scale=STANDARD_S1_SCALE_M,
                    maxPixels=1e8,
                    bestEffort=True,
                )
                return ee.Feature(None, vals).set({
                    "time_start": img.get("system:time_start"),
                    "image_id": img.get("system:index"),
                    "orbit_pass": img.get("orbitProperties_pass"),
                    "relative_orbit": img.get("relativeOrbitNumber_start"),
                })

            fc = s1_col.map(_per_s1_image).getInfo()
            parsed_scenes: list[dict[str, Any]] = []
            for feat in fc.get("features", []):
                props = feat.get("properties", {})
                ts = props.get("time_start")
                vv_lin = props.get("VV_lin")
                vh_lin = props.get("VH_lin")
                if ts is None or vv_lin is None or vv_lin <= 0:
                    continue
                vv_db = linear_to_db(vv_lin)
                vh_db = linear_to_db(vh_lin) if (vh_lin is not None and vh_lin > 0) else None
                if vv_db is None:
                    continue
                parsed_scenes.append({
                    "acquisition_date": datetime.fromtimestamp(ts / 1000.0),
                    "image_id": props.get("image_id"),
                    "orbit_pass": props.get("orbit_pass"),
                    "relative_orbit": int(props["relative_orbit"]) if props.get("relative_orbit") is not None else None,
                    "vv_lin": float(vv_lin),
                    "vh_lin": float(vh_lin) if vh_lin is not None else None,
                    "vv_db": float(vv_db),
                    "vh_db": float(vh_db) if vh_db is not None else None,
                    "incidence_angle_deg": round(float(props["angle"]), 2) if props.get("angle") is not None else None,
                })

            if not parsed_scenes:
                return None

            same_orbit_scenes, orbit_pass, relative_orbit = select_consistent_orbit_group(parsed_scenes)
            latest = same_orbit_scenes[0]
            rvi_val = compute_dual_pol_rvi(latest.get("vv_lin"), latest.get("vh_lin"))

            # Compute consistent-orbit temporal baseline using prior acquisitions in same geometry
            prior_scenes = same_orbit_scenes[1:]
            baseline_vv_db = average_db_via_linear([s["vv_db"] for s in prior_scenes]) if prior_scenes else None
            baseline_vh_db = (
                average_db_via_linear([s["vh_db"] for s in prior_scenes if s.get("vh_db") is not None])
                if prior_scenes
                else None
            )
            delta_vv_db = round(latest["vv_db"] - baseline_vv_db, 3) if baseline_vv_db is not None else None

            return {
                "source": "sentinel-1",
                "collection_id": S1_COLLECTION,
                "image_id": latest["image_id"],
                "orbit_pass": orbit_pass,
                "relative_orbit": relative_orbit,
                "incidence_angle_deg": latest.get("incidence_angle_deg"),
                "S1_VV": round(latest["vv_db"], 4),
                "S1_VH": round(latest["vh_db"], 4) if latest.get("vh_db") is not None else None,
                "S1_RVI": round(rvi_val, 4) if rvi_val is not None else None,
                "vv_linear_mean": round(latest["vv_lin"], 6),
                "vh_linear_mean": round(latest["vh_lin"], 6) if latest.get("vh_lin") is not None else None,
                "baseline_vv_db": round(baseline_vv_db, 4) if baseline_vv_db is not None else None,
                "baseline_vh_db": round(baseline_vh_db, 4) if baseline_vh_db is not None else None,
                "delta_vv_db": delta_vv_db,
                "baseline_obs_count": len(prior_scenes),
                "orbit_consistent": True,
                "rvi_formula": RVI_FORMULA_DESC,
                "rvi_expected_range": RVI_EXPECTED_RANGE,
                "spatial_scale_m": STANDARD_S1_SCALE_M,
                "averaging_domain": "linear_power_before_db",
                "acquisition_date": latest["acquisition_date"],
            }
        except Exception as e:
            logger.warning(f"Sentinel-1 fetch skipped/failed: {e}")
            return None

    def _evaluate_image_at_standard_scale(self, img_or_col, ee_geom, is_collection: bool = False):
        """
        Compute whole-field mean/min/max/stdDev AND field clear-pixel percentage at STANDARD_S2_SCALE_M (20 m).
        """
        base_img = img_or_col.median() if is_collection else img_or_col
        with_indices = self.calculate_indices(base_img)
        target_bands = OPTICAL_BANDS + ["CLEAR_MASK"]

        reducer = (
            ee.Reducer.mean()
            .combine(ee.Reducer.minMax(), sharedInputs=True)
            .combine(ee.Reducer.stdDev(), sharedInputs=True)
        )
        stats = (
            with_indices.select(target_bands)
            .reduceRegion(
                reducer=reducer,
                geometry=ee_geom,
                scale=STANDARD_S2_SCALE_M,
                maxPixels=1e9,
                bestEffort=True,
            )
            .getInfo()
        )
        return with_indices, stats

    def _get_time_series_180d(
        self,
        ee_geom,
        start_date: str,
        end_date: str,
        cloud_max: int = 20,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
        """
        Extract a genuine 180-day Sentinel-2 observation series binned into ~10-day composites.
        - Masks SCL classes + cloud edges.
        - Filters by field-geometry clear-pixel percentage.
        - Deduplicates / mosaics same-day MGRS overlaps.
        - Builds 10-day median composites where >= 2 observations exist in a bin.
        - Preserves missing observation gaps explicitly without synthetic interpolation.
        """
        try:
            end_dt = datetime.strptime(end_date[:10], "%Y-%m-%d")
        except Exception:
            end_dt = datetime.utcnow()
        window_start_dt = end_dt - timedelta(days=S2_TIME_SERIES_WINDOW_DAYS)
        try:
            req_start_dt = datetime.strptime(start_date[:10], "%Y-%m-%d")
            if req_start_dt > window_start_dt and req_start_dt <= end_dt:
                window_start_dt = req_start_dt
        except Exception:
            pass

        w_start_str = window_start_dt.strftime("%Y-%m-%d")
        w_end_str = (end_dt + timedelta(days=1)).strftime("%Y-%m-%d")

        try:
            col = self.get_sentinel2_collection(ee_geom, w_start_str, w_end_str, cloud_max)
            raw_list = col.sort("system:time_start", True).limit(80)

            def _per_tile(img):
                masked = self.calculate_indices(self.mask_clouds(img)).select(OPTICAL_BANDS + ["CLEAR_MASK"])
                vals = masked.reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=ee_geom,
                    scale=STANDARD_S2_SCALE_M,
                    maxPixels=1e8,
                    bestEffort=True,
                )
                return ee.Feature(None, vals).set({
                    "time_start": img.get("system:time_start"),
                    "image_id": img.get("system:index"),
                    "cloud_cover": img.get("CLOUDY_PIXEL_PERCENTAGE"),
                })

            fc = raw_list.map(_per_tile).getInfo()
            tile_records: list[dict[str, Any]] = []
            for feat in fc.get("features", []):
                props = feat.get("properties", {})
                ts = props.get("time_start")
                ndvi_v = props.get("NDVI")
                if ts is None or ndvi_v is None:
                    continue
                clear_frac = props.get("CLEAR_MASK")
                valid_pct = round(float(clear_frac) * 100.0, 2) if clear_frac is not None else None
                tile_records.append({
                    "acquisition_date": datetime.fromtimestamp(ts / 1000.0),
                    "image_id": props.get("image_id"),
                    "cloud_cover": float(props["cloud_cover"]) if props.get("cloud_cover") is not None else None,
                    "valid_pixel_pct": valid_pct,
                    **{b: (float(props[b]) if props.get(b) is not None else None) for b in OPTICAL_BANDS},
                })

            # Keep scenes that pass field-level usable clear-pixel threshold
            min_field_clear = max(S2_MIN_FIELD_CLEAR_PCT, min(85.0, float(100 - cloud_max)))
            usable_tiles = [
                t for t in tile_records
                if t.get("valid_pixel_pct") is None or t["valid_pixel_pct"] >= min_field_clear
            ]
            # Relax gently to S2_MIN_FIELD_CLEAR_PCT (50%) only if strict threshold yielded nothing
            if not usable_tiles:
                usable_tiles = [
                    t for t in tile_records
                    if t.get("valid_pixel_pct") is None or t["valid_pixel_pct"] >= S2_MIN_FIELD_CLEAR_PCT
                ]

            # Step A: Deduplicate / mosaic overlapping same-day MGRS tiles
            by_day = group_same_day_scenes(usable_tiles)
            daily_scenes: list[dict[str, Any]] = []
            for day_str, day_tiles in sorted(by_day.items()):
                if len(day_tiles) == 1:
                    single = dict(day_tiles[0])
                    single["day_key"] = day_str
                    single["source_tile_ids"] = [single["image_id"]] if single.get("image_id") else []
                    single["day_composite_method"] = "single_scene"
                    daily_scenes.append(single)
                else:
                    # Build genuine GEE same-day mosaic across overlapping tiles for this calendar day
                    d0 = datetime.strptime(day_str, "%Y-%m-%d")
                    d1 = (d0 + timedelta(days=1)).strftime("%Y-%m-%d")
                    day_col = self.get_sentinel2_collection(ee_geom, day_str, d1, cloud_max).map(self.mask_clouds)
                    _, day_stats = self._evaluate_image_at_standard_scale(day_col, ee_geom, is_collection=True)
                    if day_stats and day_stats.get("NDVI_mean") is not None:
                        cfrac = day_stats.get("CLEAR_MASK_mean")
                        tile_ids = [t["image_id"] for t in day_tiles if t.get("image_id")]
                        clouds = [t["cloud_cover"] for t in day_tiles if t.get("cloud_cover") is not None]
                        daily_scenes.append({
                            "day_key": day_str,
                            "acquisition_date": day_tiles[0]["acquisition_date"],
                            "image_id": tile_ids[0] if tile_ids else None,
                            "source_tile_ids": tile_ids,
                            "day_composite_method": "same_day_mgrs_mosaic",
                            "cloud_cover": round(sum(clouds) / len(clouds), 2) if clouds else None,
                            "valid_pixel_pct": round(float(cfrac) * 100.0, 2) if cfrac is not None else None,
                            **{
                                b: (float(day_stats[f"{b}_mean"]) if day_stats.get(f"{b}_mean") is not None else None)
                                for b in OPTICAL_BANDS
                            },
                        })

            # Step B: Group into ~10-day composite bins over the 180-day window (retaining empty bins as gaps)
            bins = build_10day_composite_bins(window_start_dt, end_dt, S2_COMPOSITE_BIN_DAYS)
            series: list[dict[str, Any]] = []
            gaps: list[dict[str, Any]] = []

            def _resolve_bin(bin_pair: tuple[datetime, datetime]) -> tuple[Optional[dict[str, Any]], Optional[dict[str, Any]]]:
                b_start, b_end = bin_pair
                in_bin = [d for d in daily_scenes if b_start <= d["acquisition_date"] < b_end]
                b_start_s = b_start.strftime("%Y-%m-%d")
                b_end_s = (b_end - timedelta(seconds=1)).strftime("%Y-%m-%d")

                if not in_bin:
                    return None, {
                        "period_start": b_start_s,
                        "period_end": b_end_s,
                        "status": "missing_gap",
                        "reason": "No field-clear Sentinel-2 scenes passed SCL & cloud-edge masking in window",
                    }

                if len(in_bin) == 1:
                    d = in_bin[0]
                    return {
                        "source": "sentinel-2",
                        "collection_id": S2_COLLECTION,
                        "image_id": d.get("image_id"),
                        "acquisition_date": d["acquisition_date"],
                        "cloud_cover": d.get("cloud_cover"),
                        "valid_pixel_pct": d.get("valid_pixel_pct"),
                        "observation_count": len(d.get("source_tile_ids") or [1]),
                        "composite_method": d.get("day_composite_method", "single_scene"),
                        "composite_period_start": b_start_s,
                        "composite_period_end": b_end_s,
                        "contributing_image_ids": d.get("source_tile_ids") or [],
                        **{b: d.get(b) for b in OPTICAL_BANDS},
                    }, None

                # >= 2 daily scenes in 10-day window: compute true GEE masked median composite
                b_end_excl = b_end.strftime("%Y-%m-%d")
                bin_col = (
                    self.get_sentinel2_collection(ee_geom, b_start_s, b_end_excl, cloud_max)
                    .map(self.mask_clouds)
                )
                _, comp_stats = self._evaluate_image_at_standard_scale(bin_col, ee_geom, is_collection=True)
                if not comp_stats or comp_stats.get("NDVI_mean") is None:
                    # Fallback if combined median failed: report gap rather than fabricating
                    return None, {
                        "period_start": b_start_s,
                        "period_end": b_end_s,
                        "status": "missing_gap",
                        "reason": "10-day composite returned no valid unmasked pixels",
                    }

                cfrac = comp_stats.get("CLEAR_MASK_mean")
                contrib_ids = []
                for item in in_bin:
                    contrib_ids.extend(item.get("source_tile_ids") or ([item["image_id"]] if item.get("image_id") else []))
                rep_dt = in_bin[-1]["acquisition_date"]
                clouds = [item["cloud_cover"] for item in in_bin if item.get("cloud_cover") is not None]
                return {
                    "source": "sentinel-2",
                    "collection_id": S2_COLLECTION,
                    "image_id": contrib_ids[-1] if contrib_ids else None,
                    "acquisition_date": rep_dt,
                    "cloud_cover": round(sum(clouds) / len(clouds), 2) if clouds else None,
                    "valid_pixel_pct": round(float(cfrac) * 100.0, 2) if cfrac is not None else None,
                    "observation_count": len(in_bin),
                    "composite_method": "10d_median_composite",
                    "composite_period_start": b_start_s,
                    "composite_period_end": b_end_s,
                    "contributing_image_ids": contrib_ids,
                    **{
                        b: (float(comp_stats[f"{b}_mean"]) if comp_stats.get(f"{b}_mean") is not None else None)
                        for b in OPTICAL_BANDS
                    },
                }, None

            with ThreadPoolExecutor(max_workers=6) as bin_pool:
                results = list(bin_pool.map(_resolve_bin, bins))

            for obs_entry, gap_entry in results:
                if obs_entry is not None:
                    series.append(obs_entry)
                if gap_entry is not None:
                    gaps.append(gap_entry)

            series.sort(key=lambda x: x["acquisition_date"])
            ts_meta = {
                "window_days": S2_TIME_SERIES_WINDOW_DAYS,
                "window_start": w_start_str,
                "window_end": end_dt.strftime("%Y-%m-%d"),
                "bin_days": S2_COMPOSITE_BIN_DAYS,
                "total_bins": len(bins),
                "populated_bins": len(series),
                "missing_gap_bins": len(gaps),
                "spatial_scale_m": STANDARD_S2_SCALE_M,
            }
            return series, gaps, ts_meta
        except Exception as e:
            logger.warning(f"180-day Sentinel-2 time series extraction error: {e}")
            return [], [], {"error": str(e)}

    def analyze_field(self, boundary_geojson, start_date, end_date, cloud_max=20, zone_geoms=None):
        """Full Phase 2 pipeline: Sentinel-2 (SCL/edge/mosaic/20m) + 180d 10-day composites + Sentinel-1 linear SAR."""
        import geojson

        geom = geojson.loads(boundary_geojson)
        ee_geom = ee.Geometry(geom)
        col = self.get_sentinel2_collection(ee_geom, start_date, end_date, cloud_max)

        def _fetch_s2_main():
            candidates = col.sort("system:time_start", False).limit(20)
            try:
                cand_info = candidates.map(
                    lambda img: ee.Feature(
                        None,
                        self.mask_clouds(img)
                        .select("CLEAR_MASK")
                        .reduceRegion(
                            reducer=ee.Reducer.mean(),
                            geometry=ee_geom,
                            scale=STANDARD_S2_SCALE_M,
                            maxPixels=1e8,
                            bestEffort=True,
                        ),
                    ).set({
                        "time_start": img.get("system:time_start"),
                        "image_id": img.get("system:index"),
                        "cloud_cover": img.get("CLOUDY_PIXEL_PERCENTAGE"),
                    })
                ).getInfo()
            except Exception as exc:
                logger.warning(f"Sentinel-2 candidate inspection failed: {exc}")
                return None

            feats = cand_info.get("features", []) if cand_info else []
            parsed = []
            for f in feats:
                p = f.get("properties", {})
                ts = p.get("time_start")
                cfrac = p.get("CLEAR_MASK")
                if ts is None or cfrac is None or float(cfrac) <= 0.0:
                    continue
                parsed.append({
                    "acquisition_date": datetime.fromtimestamp(ts / 1000.0),
                    "time_start": ts,
                    "image_id": p.get("image_id"),
                    "cloud_cover": float(p["cloud_cover"]) if p.get("cloud_cover") is not None else None,
                    "valid_pixel_pct": round(float(cfrac) * 100.0, 2),
                })

            if not parsed:
                return None

            min_field_clear = max(S2_MIN_FIELD_CLEAR_PCT, min(80.0, float(100 - cloud_max)))
            usable = [x for x in parsed if x["valid_pixel_pct"] >= min_field_clear]
            if not usable:
                usable = [x for x in parsed if x["valid_pixel_pct"] >= S2_MIN_FIELD_CLEAR_PCT]
            if not usable:
                return None

            # Pick latest usable calendar day; mosaic if overlapping same-day MGRS tiles cover the field
            usable.sort(key=lambda x: x["acquisition_date"], reverse=True)
            latest_day = usable[0]["acquisition_date"].strftime("%Y-%m-%d")
            day_tiles = [x for x in usable if x["acquisition_date"].strftime("%Y-%m-%d") == latest_day]

            next_day = (datetime.strptime(latest_day, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
            day_col = self.get_sentinel2_collection(ee_geom, latest_day, next_day, cloud_max).map(self.mask_clouds)

            if len(day_tiles) >= 2:
                image, stats = self._evaluate_image_at_standard_scale(day_col, ee_geom, is_collection=True)
                composite_method = "same_day_mgrs_mosaic"
                obs_count = len(day_tiles)
                tile_ids = [t["image_id"] for t in day_tiles if t.get("image_id")]
                rep = day_tiles[0]
            else:
                single_raw = col.filter(ee.Filter.eq("system:index", day_tiles[0]["image_id"])).first()
                image, stats = self._evaluate_image_at_standard_scale(self.mask_clouds(single_raw), ee_geom, is_collection=False)
                composite_method = "single_scene"
                obs_count = 1
                tile_ids = [day_tiles[0]["image_id"]] if day_tiles[0].get("image_id") else []
                rep = day_tiles[0]

            if not stats or stats.get("NDVI_mean") is None:
                return None

            cfrac = stats.get("CLEAR_MASK_mean")
            valid_pct = round(float(cfrac) * 100.0, 2) if cfrac is not None else rep["valid_pixel_pct"]

            zone_stats = {}
            if zone_geoms:
                features = [
                    ee.Feature(ee.Geometry(z_geo), {"cell_idx": idx})
                    for idx, z_geo in enumerate(zone_geoms)
                ]
                rr = image.select(OPTICAL_BANDS).reduceRegions(
                    collection=ee.FeatureCollection(features),
                    reducer=ee.Reducer.mean(),
                    scale=STANDARD_S2_SCALE_M,
                ).getInfo()

                for feat in rr.get("features", []):
                    props = feat.get("properties", {})
                    c_idx = props.get("cell_idx")
                    if c_idx is not None and props.get("NDVI") is not None:
                        zone_stats[int(c_idx)] = {
                            "NDVI": float(props["NDVI"]),
                            "NDMI": float(props["NDMI"]) if props.get("NDMI") is not None else None,
                            "NDRE": float(props["NDRE"]) if props.get("NDRE") is not None else None,
                        }

            return {
                "meta": {
                    "system:time_start": rep["time_start"],
                    "system:index": tile_ids[0] if tile_ids else rep.get("image_id"),
                    "CLOUDY_PIXEL_PERCENTAGE": rep.get("cloud_cover"),
                },
                "stats": stats,
                "zone_stats": zone_stats,
                "valid_pixel_pct": valid_pct,
                "observation_count": obs_count,
                "composite_method": composite_method,
                "contributing_image_ids": tile_ids,
            }

        with ThreadPoolExecutor(max_workers=3) as pool:
            f_s1 = pool.submit(self._get_sentinel1_stats, ee_geom, end_date)
            f_s2 = pool.submit(_fetch_s2_main)
            f_ts = pool.submit(self._get_time_series_180d, ee_geom, start_date, end_date, cloud_max)
            s1_stats = f_s1.result()
            s2_res = f_s2.result()
            time_series, ts_gaps, ts_meta = f_ts.result()

        if not s2_res and not s1_stats:
            return None

        if not s2_res:
            return {
                "optical_available": False,
                "radar_available": True,
                "source": "sentinel-1",
                "collection_id": None,
                "image_id": None,
                "s1_stats": s1_stats,
                "ndvi_stats": None,
                "evi_stats": None,
                "savi_stats": None,
                "gndvi_stats": None,
                "ndmi_stats": None,
                "ndre_stats": None,
                "zone_stats": {},
                "time_series": time_series,
                "time_series_gaps": ts_gaps,
                "time_series_meta": ts_meta,
                "is_demo": False,
                "cloud_cover": None,
                "valid_pixel_pct": None,
                "observation_count": 0,
                "composite_method": None,
                "bands_metadata": {
                    "optical_available": False,
                    "reason": "No field-clear Sentinel-2 scene passed SCL + cloud-edge masking",
                    "spatial_scale_m": STANDARD_S2_SCALE_M,
                },
                "acquisition_date": s1_stats["acquisition_date"],
            }

        meta = s2_res["meta"]
        stats = s2_res["stats"]
        zone_stats = s2_res["zone_stats"]
        time_start = meta.get("system:time_start")
        cloud_pct = meta.get("CLOUDY_PIXEL_PERCENTAGE")

        def _pack(name):
            mean_v = stats.get(f"{name}_mean")
            if mean_v is None:
                return None
            return {
                f"{name}_mean": float(mean_v),
                f"{name}_min": float(stats[f"{name}_min"]) if stats.get(f"{name}_min") is not None else None,
                f"{name}_max": float(stats[f"{name}_max"]) if stats.get(f"{name}_max") is not None else None,
                f"{name}_stdDev": float(stats[f"{name}_stdDev"]) if stats.get(f"{name}_stdDev") is not None else None,
            }

        return {
            "optical_available": True,
            "radar_available": s1_stats is not None,
            "source": "sentinel-2",
            "collection_id": S2_COLLECTION,
            "image_id": meta.get("system:index"),
            "s1_stats": s1_stats,
            "ndvi_stats": _pack("NDVI"),
            "evi_stats": _pack("EVI"),
            "savi_stats": _pack("SAVI"),
            "gndvi_stats": _pack("GNDVI"),
            "ndmi_stats": _pack("NDMI"),
            "ndre_stats": _pack("NDRE"),
            "zone_stats": zone_stats,
            "time_series": time_series,
            "time_series_gaps": ts_gaps,
            "time_series_meta": ts_meta,
            "is_demo": False,
            "cloud_cover": float(cloud_pct) if cloud_pct is not None else None,
            "valid_pixel_pct": s2_res["valid_pixel_pct"],
            "observation_count": s2_res["observation_count"],
            "composite_method": s2_res["composite_method"],
            "bands_metadata": {
                "scale_m": STANDARD_S2_SCALE_M,
                "zone_scale_m": STANDARD_S2_SCALE_M,
                "scl_masked_classes": list(S2_MASKED_SCL_CLASSES),
                "cloud_edge_dilation_m": S2_CLOUD_EDGE_RADIUS_M,
                "valid_pixel_pct": s2_res["valid_pixel_pct"],
                "observation_count": s2_res["observation_count"],
                "composite_method": s2_res["composite_method"],
                "contributing_image_ids": s2_res["contributing_image_ids"],
                "time_series_meta": ts_meta,
            },
            "acquisition_date": datetime.fromtimestamp(time_start / 1000.0),
        }

    def get_tile_url(self, image, vis_params):
        """Get tile URL for map display."""
        map_id = image.getMapId(vis_params)
        return map_id["tile_fetcher"].url_format

    def get_index_stats(self, image, geometry, index_name):
        """Get statistics for an index within a geometry at standardized 20 m scale."""
        return image.select(index_name).reduceRegion(
            reducer=ee.Reducer.mean().combine(ee.Reducer.minMax(), sharedInputs=True).combine(ee.Reducer.stdDev(), sharedInputs=True),
            geometry=geometry,
            scale=STANDARD_S2_SCALE_M,
            maxPixels=1e9,
        ).getInfo()

    def get_pixel_values(self, image, geometry, index_name, scale=STANDARD_S2_SCALE_M):
        """Get array of pixel values for ML processing."""
        return np.array([])


class DemoGEEService:
    def __init__(self):
        self._initialized = True
        logger.info("[DEMO] Simulated Demo GEE Service initialized")

    def initialize(self):
        return True

    def analyze_field(self, boundary_geojson, start_date, end_date, cloud_max=20, zone_geoms=None):
        """Simulate [DEMO] 180-day ~10-day S2 series + linear S1 SAR with strict demo provenance."""
        logger.info("[DEMO] Generating simulated data — not from actual satellite imagery")

        ndvi_mean = random.uniform(0.55, 0.78)
        ndmi_mean = ndvi_mean - 0.12
        ndre_mean = ndvi_mean - 0.18
        evi_mean = ndvi_mean * 0.88
        savi_mean = ndvi_mean * 0.82
        gndvi_mean = ndvi_mean * 0.92

        zone_stats = {}
        if zone_geoms:
            for idx in range(len(zone_geoms)):
                if idx in (2, 5, 10) and len(zone_geoms) > 2:
                    zone_stats[idx] = {
                        "NDVI": max(0.15, ndvi_mean - random.uniform(0.22, 0.35)),
                        "NDMI": max(-0.4, ndmi_mean - random.uniform(0.20, 0.30)),
                        "NDRE": max(0.10, ndre_mean - random.uniform(0.15, 0.25)),
                    }
                else:
                    zone_stats[idx] = {
                        "NDVI": min(0.95, max(0.2, ndvi_mean + random.uniform(-0.06, 0.07))),
                        "NDMI": min(0.8, max(-0.3, ndmi_mean + random.uniform(-0.05, 0.05))),
                        "NDRE": min(0.85, max(0.1, ndre_mean + random.uniform(-0.05, 0.05))),
                    }

        now = datetime.utcnow()
        s2_date = now - timedelta(days=2)
        s1_date = now - timedelta(days=1)

        curve = [0.22, 0.31, 0.44, 0.58, 0.72, 0.76, 0.69, ndvi_mean]
        time_series = []
        for i, val in enumerate(curve):
            dt = s2_date - timedelta(days=(len(curve) - 1 - i) * 18)
            time_series.append({
                "source": "demo-simulation",
                "collection_id": "DEMO/SIMULATED",
                "image_id": f"demo_s2_{dt.strftime('%Y%m%d')}",
                "acquisition_date": dt,
                "cloud_cover": round(random.uniform(1, 12), 1),
                "valid_pixel_pct": 94.0,
                "observation_count": 2 if i % 2 == 0 else 1,
                "composite_method": "demo_10d_simulated",
                "NDVI": round(val, 4),
                "EVI": round(val * 0.88, 4),
                "SAVI": round(val * 0.82, 4),
                "GNDVI": round(val * 0.92, 4),
                "NDMI": round(val - 0.14, 4),
                "NDRE": round(val - 0.18, 4),
            })

        s1_vv_db = -10.5
        s1_vh_db = -16.8
        vv_lin = 10 ** (s1_vv_db / 10.0)
        vh_lin = 10 ** (s1_vh_db / 10.0)
        rvi = compute_dual_pol_rvi(vv_lin, vh_lin)

        return {
            "optical_available": True,
            "radar_available": True,
            "source": "demo-simulation",
            "collection_id": "DEMO/SIMULATED",
            "image_id": f"demo_s2_{s2_date.strftime('%Y%m%d')}",
            "s1_stats": {
                "source": "demo-simulation",
                "collection_id": "DEMO/SIMULATED",
                "image_id": f"demo_s1_{s1_date.strftime('%Y%m%d')}",
                "orbit_pass": "DESCENDING",
                "relative_orbit": 63,
                "incidence_angle_deg": 37.8,
                "S1_VV": s1_vv_db,
                "S1_VH": s1_vh_db,
                "S1_RVI": round(rvi, 4) if rvi is not None else None,
                "vv_linear_mean": round(vv_lin, 6),
                "vh_linear_mean": round(vh_lin, 6),
                "baseline_vv_db": -11.2,
                "delta_vv_db": 0.7,
                "baseline_obs_count": 3,
                "orbit_consistent": True,
                "rvi_formula": RVI_FORMULA_DESC,
                "rvi_expected_range": RVI_EXPECTED_RANGE,
                "spatial_scale_m": STANDARD_S1_SCALE_M,
                "averaging_domain": "linear_power_before_db",
                "acquisition_date": s1_date,
            },
            "ndvi_stats": {"NDVI_mean": ndvi_mean, "NDVI_min": 0.28, "NDVI_max": 0.85, "NDVI_stdDev": 0.11},
            "evi_stats": {"EVI_mean": evi_mean, "EVI_min": 0.22, "EVI_max": 0.78, "EVI_stdDev": 0.09},
            "savi_stats": {"SAVI_mean": savi_mean, "SAVI_min": 0.24, "SAVI_max": 0.74, "SAVI_stdDev": 0.08},
            "gndvi_stats": {"GNDVI_mean": gndvi_mean, "GNDVI_min": 0.30, "GNDVI_max": 0.80, "GNDVI_stdDev": 0.09},
            "ndmi_stats": {"NDMI_mean": ndmi_mean, "NDMI_min": -0.05, "NDMI_max": 0.55, "NDMI_stdDev": 0.08},
            "ndre_stats": {"NDRE_mean": ndre_mean, "NDRE_min": 0.15, "NDRE_max": 0.62, "NDRE_stdDev": 0.07},
            "zone_stats": zone_stats,
            "time_series": time_series,
            "time_series_gaps": [],
            "time_series_meta": {"window_days": S2_TIME_SERIES_WINDOW_DAYS, "bin_days": S2_COMPOSITE_BIN_DAYS},
            "is_demo": True,
            "cloud_cover": round(random.uniform(1.0, 9.0), 1),
            "valid_pixel_pct": 95.0,
            "observation_count": 1,
            "composite_method": "demo_simulated",
            "bands_metadata": {
                "scale_m": STANDARD_S2_SCALE_M,
                "is_demo": True,
                "note": "Simulated demo observation",
            },
            "acquisition_date": s2_date,
        }

    def get_index_stats(self, image, geometry, index_name):
        return {}


def get_gee_service():
    """Return real GEEService or DemoGEEService depending on config DEMO_MODE."""
    if settings.DEMO_MODE:
        return DemoGEEService()
    svc = GEEService()
    if svc.initialize():
        return svc
    logger.warning("[WARN] Real GEE initialization failed, falling back to DemoGEEService")
    return DemoGEEService()
