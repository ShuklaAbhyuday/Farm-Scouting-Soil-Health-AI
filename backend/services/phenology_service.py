"""
Seasonal phenology segmentation, rate-of-change (NDVI/week), minimum-evidence gating,
multi-observation senescence/harvest confirmation, and contextual crop calendars.

Design principles:
- Multi-year observations are partitioned by temporal gaps (> 60 days) so prior-year
  scenes cannot become the peak of a later crop cycle.
- Minimum sample count (>= 4) and time span (>= 21 days) are enforced before stage labeling.
- Senescence / probable harvesting requires >= 2 consecutive declining observations with a
  meaningful cumulative or weekly decline, never a single noisy dip.
- Crop calendars provide seasonal context only and never prove actual crop identity or stage.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

MIN_SEASON_OBSERVATIONS = 4
MIN_SEASON_SPAN_DAYS = 21
SEASON_GAP_DAYS = 60

CROP_CALENDAR_CONTEXT: dict[str, list[tuple[tuple[int, ...], str]]] = {
    "wheat": [
        ((10, 11, 12), "Typical South Asian Rabi sowing/emergence window (Oct-Dec); spectral trajectory remains primary evidence."),
        ((1, 2), "Typical Rabi vegetative-to-heading window (Jan-Feb); verify against observed NDVI curve."),
        ((3, 4), "Typical Rabi grain-fill/maturation/harvest window (Mar-Apr); confirm with consecutive spectral declines."),
        ((5, 6, 7, 8, 9), "Outside primary Rabi wheat window in many regions (summer/Kharif fallow or rotation likely)."),
    ],
    "rice": [
        ((6, 7, 8), "Typical Kharif transplanting/vegetative window (Jun-Aug); verify standing water vs canopy."),
        ((9, 10, 11), "Typical Kharif reproductive/ripening/harvest window (Sep-Nov); confirm with SAR/optical trend."),
        ((12, 1, 2, 3, 4, 5), "Off-main Kharif window unless irrigated Rabi/Boro rice is practiced."),
    ],
    "maize": [
        ((6, 7, 8, 9), "Typical Kharif maize vegetative-to-grain-fill window (Jun-Sep)."),
        ((10, 11, 12, 1, 2, 3), "Possible Rabi/winter maize or post-Kharif rotation depending on irrigation."),
    ],
    "soybean": [
        ((6, 7, 8, 9), "Typical Kharif soybean vegetative and pod-fill window (Jun-Sep)."),
        ((10, 11), "Typical late-Kharif soybean maturity/harvest or post-harvest fallow transition (Oct-Nov)."),
    ],
    "cotton": [
        ((5, 6, 7, 8), "Typical early-to-mid vegetative cotton window (May-Aug)."),
        ((9, 10, 11, 12), "Typical boll-opening/picking window (Sep-Dec)."),
    ],
}


def get_crop_calendar_context(crop_type: Optional[str], latest_dt: Optional[datetime]) -> dict[str, Any]:
    """Return contextual calendar notes without treating calendar date as proof of crop stage."""
    month = latest_dt.month if latest_dt else None
    key = (crop_type or "").strip().lower()
    entries = CROP_CALENDAR_CONTEXT.get(key)

    note = (
        f"No region-specific crop calendar configured for '{crop_type or 'unspecified'}'; "
        "satellite trajectory is used solely as observational context."
    )
    if entries and month is not None:
        for months, desc in entries:
            if month in months:
                note = desc
                break

    return {
        "crop_type": crop_type,
        "observation_month": month,
        "context_note": note,
        "is_proof_of_stage": False,
        "limitation": "Crop calendars reflect regional norms only and cannot verify field-level sowing date, cultivar, or actual phenological stage.",
    }


def segment_crop_seasons(points: list[tuple[datetime, float]]) -> list[list[tuple[datetime, float]]]:
    """
    Partition chronological (datetime, ndvi) pairs into separate growing seasons/cycles.
    Any gap exceeding SEASON_GAP_DAYS (60 days) starts a new season segment.
    """
    if not points:
        return []
    ordered = sorted(points, key=lambda x: x[0])
    seasons: list[list[tuple[datetime, float]]] = [[ordered[0]]]
    for pt in ordered[1:]:
        gap_days = (pt[0] - seasons[-1][-1][0]).total_seconds() / 86400.0
        if gap_days > SEASON_GAP_DAYS:
            seasons.append([pt])
        else:
            seasons[-1].append(pt)
    return seasons


def compute_weekly_ndvi_rate(points: list[tuple[datetime, float]]) -> tuple[Optional[float], Optional[float], Optional[int]]:
    """
    Compute raw delta NDVI and elapsed-time-normalized NDVI change per week
    between the latest two distinct observations.
    Returns (ndvi_change, ndvi_change_per_week, elapsed_days).
    """
    if len(points) < 2:
        return None, None, None
    prev_dt, prev_val = points[-2]
    latest_dt, latest_val = points[-1]
    elapsed_days = (latest_dt - prev_dt).total_seconds() / 86400.0
    if elapsed_days < 1.0:
        return None, None, None
    delta = latest_val - prev_val
    rate_per_week = delta / (elapsed_days / 7.0)
    return round(delta, 4), round(rate_per_week, 4), int(round(elapsed_days))


def count_consecutive_declines(points: list[tuple[datetime, float]], min_step_drop: float = 0.005) -> int:
    """Count consecutive trailing intervals where NDVI strictly declined by at least min_step_drop."""
    if len(points) < 2:
        return 0
    streak = 0
    for i in range(len(points) - 1, 0, -1):
        if points[i - 1][1] - points[i][1] >= min_step_drop:
            streak += 1
        else:
            break
    return streak


def analyze_seasonal_phenology(
    points: list[tuple[datetime, float]],
    crop_type: Optional[str] = None,
) -> dict[str, Any]:
    """
    Analyze phenology strictly within the latest temporal season segment.
    Multi-year prior seasons are summarized separately and excluded from current-season peak NDVI.
    """
    if not points:
        return {
            "stage": "No data",
            "stage_confidence": "unavailable",
            "land_status": "Unknown",
            "peak_ndvi": None,
            "peak_date": None,
            "latest_date": None,
            "season_start_date": None,
            "season_span_days": 0,
            "observation_count": 0,
            "total_archive_observations": 0,
            "season_count": 0,
            "previous_seasons": [],
            "ndvi_change": None,
            "ndvi_change_per_week": None,
            "elapsed_days_since_prev": None,
            "consecutive_declines": 0,
            "crop_calendar_context": get_crop_calendar_context(crop_type, None),
            "limitation": "No valid cloud-free optical observations available.",
        }

    seasons = segment_crop_seasons(points)
    current = seasons[-1]
    previous = seasons[:-1]

    prev_summaries = []
    for s in previous:
        s_peak_dt, s_peak_val = max(s, key=lambda x: x[1])
        prev_summaries.append({
            "start_date": s[0][0].strftime("%Y-%m-%d"),
            "end_date": s[-1][0].strftime("%Y-%m-%d"),
            "observation_count": len(s),
            "peak_ndvi": round(s_peak_val, 4),
            "peak_date": s_peak_dt.strftime("%Y-%m-%d"),
        })

    season_start_dt = current[0][0]
    latest_dt, latest_val = current[-1]
    peak_dt, peak_val = max(current, key=lambda x: x[1])
    span_days = int(round((latest_dt - season_start_dt).total_seconds() / 86400.0))

    ndvi_change, ndvi_change_per_week, elapsed_days = compute_weekly_ndvi_rate(current)
    decline_streak = count_consecutive_declines(current)

    if latest_val < 0.22:
        land_status = "Bare Soil / Fallow or Early Emergence"
    elif latest_val < 0.40:
        land_status = "Sparse / Developing Canopy"
    else:
        land_status = "Active Vegetated Crop"

    # Enforce minimum observation-count (>= 4) and minimum time-span (>= 21 days)
    if len(current) < MIN_SEASON_OBSERVATIONS or span_days < MIN_SEASON_SPAN_DAYS:
        stage = "Insufficient temporal evidence"
        stage_confidence = "insufficient"
        limitation = (
            f"Current season has {len(current)} observation(s) over {span_days} day(s); "
            f"at least {MIN_SEASON_OBSERVATIONS} observations spanning >= {MIN_SEASON_SPAN_DAYS} days "
            "are required to classify growth stage reliably."
        )
    else:
        stage_confidence = "moderate"
        cumulative_drop_from_peak = peak_val - latest_val
        if peak_val < 0.22 and latest_val < 0.22:
            stage = "Bare Soil / Fallow or Pre-Emergence"
        elif ndvi_change_per_week is not None and ndvi_change_per_week >= 0.025:
            stage = "Vegetative Green-Up"
        elif (
            decline_streak >= 2
            and cumulative_drop_from_peak >= 0.08
            and peak_val >= 0.35
            and latest_val < 0.25
        ):
            stage = "Probable Senescence / Harvest Transition"
        elif decline_streak >= 2 and cumulative_drop_from_peak >= 0.05:
            stage = "Multi-Observation Canopy Decline (Monitor Senescence)"
        elif latest_val >= peak_val - 0.05 and latest_val >= 0.45:
            stage = "Peak Canopy Vigor"
        elif latest_val < 0.25:
            stage = "Low Vigor / Sparse Emergence"
        else:
            stage = "Mid-Season Steady / Transitional"

        limitation = (
            "Phenology labels reflect current-season NDVI trajectory only (isolated from prior seasons "
            f"by gaps > {SEASON_GAP_DAYS} days); single-point dips never trigger harvest/senescence."
        )

    return {
        "stage": stage,
        "stage_confidence": stage_confidence,
        "land_status": land_status,
        "peak_ndvi": round(peak_val, 4),
        "peak_date": peak_dt.strftime("%Y-%m-%d"),
        "latest_date": latest_dt.strftime("%Y-%m-%d"),
        "season_start_date": season_start_dt.strftime("%Y-%m-%d"),
        "season_span_days": span_days,
        "observation_count": len(current),
        "total_archive_observations": len(points),
        "season_count": len(seasons),
        "previous_seasons": prev_summaries,
        "ndvi_change": ndvi_change,
        "ndvi_change_per_week": ndvi_change_per_week,
        "elapsed_days_since_prev": elapsed_days,
        "consecutive_declines": decline_streak,
        "crop_calendar_context": get_crop_calendar_context(crop_type, latest_dt),
        "limitation": limitation,
    }
