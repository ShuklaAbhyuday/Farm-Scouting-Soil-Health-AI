"""
Sentinel-1 SAR radiometric conversion, dual-polarization RVI, orbit filtering,
and relative temporal backscatter interpretation utilities.

Formulas & Units:
- Input GRD backscatter sigma0 in dB is converted to linear power BEFORE spatial averaging:
    sigma0_lin = 10 ** (sigma0_dB / 10.0)
- Spatially averaged linear power is converted back to dB for presentation:
    sigma0_dB_mean = 10.0 * log10(mean(sigma0_lin))
- Dual-polarization Radar Vegetation Index (dual-pol VV+VH approximation):
    RVI_dual = (4.0 * VH_lin_mean) / (VV_lin_mean + VH_lin_mean)
  Expected physical range for agricultural canopies: ~0.05 to 1.50
  (unlike quad-pol RVI bounded to [0, 1], dual-pol 4*VH/(VV+VH) can exceed 1.0 when
  volume/cross-pol depolarization approaches co-pol; non-physical negatives are bounded at 0.0
  and extreme outliers capped at 2.0 without clipping valid [1.0, 1.5] canopy signals).
"""
from __future__ import annotations

import math
from typing import Any, Optional

RVI_FORMULA_DESC = "4 * VH_linear / (VV_linear + VH_linear)"
RVI_EXPECTED_RANGE = "0.0 to ~1.5 (typical crops 0.15-1.10; non-physical bounds [0.0, 2.0])"


def db_to_linear(db_val: Optional[float]) -> Optional[float]:
    """Convert backscatter sigma0 from decibels (dB) to linear power ratio."""
    if db_val is None:
        return None
    return 10.0 ** (float(db_val) / 10.0)


def linear_to_db(lin_val: Optional[float]) -> Optional[float]:
    """Convert positive linear power ratio back to decibels (dB)."""
    if lin_val is None or float(lin_val) <= 0.0:
        return None
    return 10.0 * math.log10(float(lin_val))


def average_db_via_linear(db_values: list[float]) -> Optional[float]:
    """Average dB backscatter samples physically in linear power domain, then return dB."""
    lin_vals = [db_to_linear(v) for v in db_values if v is not None]
    valid = [x for x in lin_vals if x is not None and x > 0.0]
    if not valid:
        return None
    return linear_to_db(sum(valid) / len(valid))


def compute_dual_pol_rvi(vv_lin: Optional[float], vh_lin: Optional[float]) -> Optional[float]:
    """
    Compute dual-polarization Radar Vegetation Index from spatially averaged linear power:
        RVI = 4 * VH_lin / (VV_lin + VH_lin)
    Returns None if inputs are invalid/non-positive; retains valid values in [0.0, 2.0].
    """
    if vv_lin is None or vh_lin is None:
        return None
    denom = float(vv_lin) + float(vh_lin)
    if denom <= 0.0 or float(vv_lin) <= 0.0 or float(vh_lin) < 0.0:
        return None
    raw = (4.0 * float(vh_lin)) / denom
    return max(0.0, min(2.0, raw))


def select_consistent_orbit_group(scenes: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], Optional[str], Optional[int]]:
    """
    Filter Sentinel-1 scenes to a single consistent viewing geometry
    (orbit_pass + relative_orbit) matching the latest acquisition.
    Returns (filtered_scenes_desc, selected_orbit_pass, selected_relative_orbit).
    """
    if not scenes:
        return [], None, None

    ordered = sorted(scenes, key=lambda s: s["acquisition_date"], reverse=True)
    target = ordered[0]
    target_pass = target.get("orbit_pass")
    target_rel = target.get("relative_orbit")

    if target_pass is None and target_rel is None:
        return ordered, None, None

    matched = [
        s for s in ordered
        if (target_pass is None or s.get("orbit_pass") == target_pass)
        and (target_rel is None or s.get("relative_orbit") == target_rel)
    ]
    return matched, target_pass, target_rel


def classify_surface_wetness_relative(
    s1_vv_db: Optional[float],
    delta_vv_db: Optional[float],
    baseline_count: int = 0,
    orbit_consistent: bool = True,
    ndmi: Optional[float] = None,
    ndvi: Optional[float] = None,
) -> dict[str, Any]:
    """
    Classify surface conditions using relative temporal Sentinel-1 VV backscatter change
    within a consistent orbit geometry rather than fixed absolute dB soil-moisture thresholds.
    Explicitly states that radar backscatter is a proxy and not a direct soil moisture measurement.
    """
    limitation = (
        "Sentinel-1 sigma0 VV backscatter responds to dielectric constant (moisture), surface roughness, "
        "and vegetation volume; it is a relative radar proxy and NOT a direct soil moisture measurement."
    )

    if s1_vv_db is None:
        if ndmi is not None:
            if ndmi < -0.05:
                status = "Low Optical Canopy Water Signal (NDMI Proxy; No Radar)"
            elif ndmi > 0.35:
                status = "High Optical Canopy Water Signal (NDMI Proxy; No Radar)"
            else:
                status = "Moderate Optical Canopy Water Signal (NDMI Proxy; No Radar)"
        else:
            status = "Radar Unavailable (No Surface Wetness Proxy)"
        return {
            "status": status,
            "method": "optical_ndmi_fallback" if ndmi is not None else "unavailable",
            "delta_vv_db": None,
            "baseline_obs_count": 0,
            "orbit_consistent": False,
            "limitation": limitation,
        }

    if not orbit_consistent or baseline_count < 2 or delta_vv_db is None:
        return {
            "status": "Insufficient Same-Orbit Radar Baseline (Raw Backscatter Only; Change Unavailable)",
            "method": "insufficient_same_orbit_baseline",
            "delta_vv_db": round(delta_vv_db, 2) if delta_vv_db is not None else None,
            "baseline_obs_count": int(baseline_count),
            "orbit_consistent": bool(orbit_consistent),
            "limitation": limitation,
        }

    if delta_vv_db <= -3.0:
        if ndvi is not None and ndvi < 0.25 and s1_vv_db < -16.0:
            status = "Sharp Backscatter Drop vs. Orbit Baseline (Possible Smooth Ponding / Bare Dry Proxy)"
        else:
            status = "Sharp Backscatter Drop vs. Orbit Baseline (Possible Surface Drying / Smoothness Shift Proxy)"
    elif delta_vv_db <= -1.5:
        status = "Below-Baseline Backscatter Change (Relative Drier Surface or Canopy Shift Proxy)"
    elif delta_vv_db >= 2.0:
        status = "Elevated Backscatter vs. Orbit Baseline (Relative Wetness / Roughness Increase Proxy)"
    else:
        status = "Near-Baseline Same-Orbit Backscatter (Stable Relative Surface Proxy)"

    return {
        "status": status,
        "method": "same_orbit_temporal_delta_vv",
        "delta_vv_db": round(delta_vv_db, 2),
        "baseline_obs_count": int(baseline_count),
        "orbit_consistent": True,
        "limitation": limitation,
    }
