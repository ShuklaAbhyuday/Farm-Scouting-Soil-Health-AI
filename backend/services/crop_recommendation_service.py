from __future__ import annotations

from typing import Any, Optional


CROP_PROFILES = [
    {
        "crop": "Wheat",
        "emoji": "🌾",
        "season": "Rabi",
        "ph_range": (6.0, 7.5),
        "n_ideal": (40, 120),
        "p_ideal": (20, 60),
        "k_ideal": (100, 220),
        "textures": ["Loamy", "Clay Loam", "Silty Clay"],
        "moisture_pref": "medium",
        "nitrogen_fixer": False,
        "summary": "Cool-season cereal thriving in neutral, well-drained loamy soils with balanced NPK.",
    },
    {
        "crop": "Rice (Paddy)",
        "emoji": "🍚",
        "season": "Kharif",
        "ph_range": (5.5, 7.0),
        "n_ideal": (50, 130),
        "p_ideal": (20, 55),
        "k_ideal": (90, 200),
        "textures": ["Clay", "Clay Loam", "Silty Clay", "Loamy"],
        "moisture_pref": "high",
        "nitrogen_fixer": False,
        "summary": "High-moisture crop suited to water-retentive clay and clay-loam soils.",
    },
    {
        "crop": "Maize (Corn)",
        "emoji": "🌽",
        "season": "Kharif",
        "ph_range": (5.8, 7.2),
        "n_ideal": (60, 150),
        "p_ideal": (25, 65),
        "k_ideal": (110, 230),
        "textures": ["Loamy", "Sandy Loam", "Clay Loam"],
        "moisture_pref": "medium",
        "nitrogen_fixer": False,
        "summary": "Nutrient-demanding cereal crop that rewards fertile, well-aerated loamy soils.",
    },
    {
        "crop": "Soybean",
        "emoji": "🫘",
        "season": "Kharif",
        "ph_range": (6.0, 7.2),
        "n_ideal": (10, 50),
        "p_ideal": (25, 60),
        "k_ideal": (110, 220),
        "textures": ["Loamy", "Clay Loam", "Sandy Loam"],
        "moisture_pref": "medium",
        "nitrogen_fixer": True,
        "summary": "Nitrogen-fixing legume ideal for restoring low-nitrogen soils while producing high-protein yield.",
    },
    {
        "crop": "Chickpea (Gram)",
        "emoji": "🫛",
        "season": "Rabi",
        "ph_range": (6.0, 8.0),
        "n_ideal": (10, 45),
        "p_ideal": (20, 55),
        "k_ideal": (90, 190),
        "textures": ["Sandy Loam", "Loamy", "Clay Loam"],
        "moisture_pref": "low",
        "nitrogen_fixer": True,
        "summary": "Drought-tolerant Rabi pulse that fixes atmospheric nitrogen and performs well in low-N or low-moisture soils.",
    },
    {
        "crop": "Mustard",
        "emoji": "🌼",
        "season": "Rabi",
        "ph_range": (6.0, 7.8),
        "n_ideal": (35, 95),
        "p_ideal": (18, 50),
        "k_ideal": (80, 180),
        "textures": ["Sandy Loam", "Loamy"],
        "moisture_pref": "low",
        "nitrogen_fixer": False,
        "summary": "Hardy oilseed crop well adapted to light-to-medium soils and moderate irrigation.",
    },
    {
        "crop": "Cotton",
        "emoji": "☁️",
        "season": "Kharif",
        "ph_range": (6.0, 8.2),
        "n_ideal": (45, 115),
        "p_ideal": (20, 55),
        "k_ideal": (120, 250),
        "textures": ["Clay Loam", "Clay", "Loamy"],
        "moisture_pref": "medium",
        "nitrogen_fixer": False,
        "summary": "Deep-rooted fiber crop suited to black/clay-loam soils with slightly neutral-to-alkaline pH.",
    },
    {
        "crop": "Groundnut",
        "emoji": "🥜",
        "season": "Kharif",
        "ph_range": (5.8, 7.0),
        "n_ideal": (12, 45),
        "p_ideal": (22, 55),
        "k_ideal": (95, 190),
        "textures": ["Sandy", "Sandy Loam", "Loamy"],
        "moisture_pref": "low",
        "nitrogen_fixer": True,
        "summary": "Nitrogen-fixing oilseed preferring friable sandy/loamy soils for peg penetration.",
    },
    {
        "crop": "Sugarcane",
        "emoji": "🎋",
        "season": "Year-round",
        "ph_range": (6.0, 7.8),
        "n_ideal": (70, 160),
        "p_ideal": (30, 75),
        "k_ideal": (130, 260),
        "textures": ["Loamy", "Clay Loam", "Silty Clay"],
        "moisture_pref": "high",
        "nitrogen_fixer": False,
        "summary": "Long-duration cash crop requiring rich NPK reserves and reliable moisture.",
    },
    {
        "crop": "Vegetables / Potato",
        "emoji": "🥔",
        "season": "Rabi",
        "ph_range": (5.2, 6.8),
        "n_ideal": (50, 125),
        "p_ideal": (30, 70),
        "k_ideal": (130, 260),
        "textures": ["Sandy Loam", "Loamy"],
        "moisture_pref": "medium",
        "nitrogen_fixer": False,
        "summary": "High-value horticultural option thriving in slightly acidic, loose loamy soils with rich potassium.",
    },
]

_LEVEL_TO_NUM = {
    "n": {"low": 15.0, "medium": 55.0, "high": 100.0},
    "p": {"low": 12.0, "medium": 35.0, "high": 65.0},
    "k": {"low": 75.0, "medium": 145.0, "high": 225.0},
}


def _resolve_nutrient(value: Optional[float], level: Optional[str], kind: str) -> tuple[float, str]:
    if value is not None:
        if kind == "n":
            lvl = "low" if value < 25 else ("high" if value > 80 else "medium")
        elif kind == "p":
            lvl = "low" if value < 18 else ("high" if value > 50 else "medium")
        else:
            lvl = "low" if value < 100 else ("high" if value > 200 else "medium")
        return float(value), lvl
    norm_lvl = (level or "medium").lower()
    return _LEVEL_TO_NUM[kind].get(norm_lvl, _LEVEL_TO_NUM[kind]["medium"]), norm_lvl


def _score_range(val: float, low: float, high: float, margin: float) -> float:
    if low <= val <= high:
        return 1.0
    dist = (low - val) if val < low else (val - high)
    return max(0.0, 1.0 - dist / margin)


def recommend_crops(
    nitrogen_value: Optional[float] = None,
    nitrogen_level: Optional[str] = "medium",
    phosphorus_value: Optional[float] = None,
    phosphorus_level: Optional[str] = "medium",
    potassium_value: Optional[float] = None,
    potassium_level: Optional[str] = "medium",
    ph_value: float = 6.8,
    moisture_level: str = "medium",
    soil_texture: str = "Loamy",
    season: str = "All",
    ndmi_mean: Optional[float] = None,
    is_validated: bool = False,
) -> list[dict[str, Any]]:
    n_val, n_lvl = _resolve_nutrient(nitrogen_value, nitrogen_level, "n")
    p_val, p_lvl = _resolve_nutrient(phosphorus_value, phosphorus_level, "p")
    k_val, k_lvl = _resolve_nutrient(potassium_value, potassium_level, "k")

    eff_moisture = (moisture_level or "medium").lower()
    if ndmi_mean is not None and not moisture_level:
        eff_moisture = "low" if ndmi_mean < 0.05 else ("high" if ndmi_mean > 0.45 else "medium")

    results = []
    for prof in CROP_PROFILES:
        if season and season != "All" and prof["season"] not in (season, "Year-round"):
            continue

        ph_score = _score_range(ph_value, prof["ph_range"][0], prof["ph_range"][1], 1.8)
        n_score = _score_range(n_val, prof["n_ideal"][0], prof["n_ideal"][1], 65.0)
        p_score = _score_range(p_val, prof["p_ideal"][0], prof["p_ideal"][1], 40.0)
        k_score = _score_range(k_val, prof["k_ideal"][0], prof["k_ideal"][1], 110.0)

        texture_score = 1.0 if soil_texture in prof["textures"] else 0.55
        if prof["moisture_pref"] == eff_moisture:
            moisture_score = 1.0
        elif "medium" in (prof["moisture_pref"], eff_moisture):
            moisture_score = 0.72
        else:
            moisture_score = 0.40

        raw = (
            0.28 * ph_score
            + 0.22 * n_score
            + 0.14 * p_score
            + 0.14 * k_score
            + 0.12 * texture_score
            + 0.10 * moisture_score
        )
        # Bonus for nitrogen-fixing legumes when soil nitrogen is low
        if prof["nitrogen_fixer"] and n_lvl == "low":
            raw = min(0.99, raw + 0.08)

        pct = int(round(min(99, max(20, raw * 100))))

        reasons = []
        if ph_score >= 0.85:
            reasons.append(f"pH {ph_value:.1f} fits optimal range ({prof['ph_range'][0]}–{prof['ph_range'][1]})")
        elif ph_score < 0.6:
            reasons.append(f"pH {ph_value:.1f} is outside ideal ({prof['ph_range'][0]}–{prof['ph_range'][1]}); pH amendment advised")

        if prof["nitrogen_fixer"] and n_lvl == "low":
            reasons.append("Nitrogen-fixing legume helps recover low soil Nitrogen")
        elif n_score >= 0.8:
            reasons.append("Soil Nitrogen level aligns with crop demand")
        elif n_val < prof["n_ideal"][0]:
            reasons.append("Needs supplemental Nitrogen before or at planting")

        if soil_texture in prof["textures"]:
            reasons.append(f"{soil_texture} texture suits root establishment")

        if moisture_score >= 0.9:
            reasons.append(f"Matches {eff_moisture} field moisture profile")

        if pct >= 82:
            match_label = "Highly Recommended"
        elif pct >= 68:
            match_label = "Good Fit"
        else:
            match_label = "Moderate Fit"

        care_notes = prof["summary"]
        if not is_validated:
            care_notes += " Validate NPK levels with a lab soil test before finalizing fertilizer dosage."

        results.append({
            "crop": prof["crop"],
            "emoji": prof["emoji"],
            "season": prof["season"],
            "suitability_score": pct,
            "match_label": match_label,
            "nitrogen_fixer": prof["nitrogen_fixer"],
            "reasons": reasons,
            "care_notes": care_notes,
        })

    results.sort(key=lambda x: x["suitability_score"], reverse=True)
    return results


def analyze_soil_sample(sample: Any) -> dict[str, Any]:
    """Produce an immediate diagnostic result card for a submitted SoilSample."""
    n_val, n_lvl = _resolve_nutrient(sample.nitrogen_value, sample.nitrogen_level, "n")
    p_val, p_lvl = _resolve_nutrient(sample.phosphorus_value, sample.phosphorus_level, "p")
    k_val, k_lvl = _resolve_nutrient(sample.potassium_value, sample.potassium_level, "k")
    ph = sample.ph_value if sample.ph_value is not None else 7.0

    if ph < 5.5:
        ph_status = "Strongly Acidic"
    elif ph < 6.0:
        ph_status = "Slightly Acidic"
    elif ph <= 7.5:
        ph_status = "Optimal Neutral"
    elif ph <= 8.2:
        ph_status = "Slightly Alkaline"
    else:
        ph_status = "Strongly Alkaline"

    # Compute overall fertility score (0-100)
    lvl_pts = {"low": 50, "medium": 85, "high": 90}
    ph_pts = 95 if 6.0 <= ph <= 7.5 else (75 if 5.5 <= ph <= 8.0 else 50)
    fertility_score = round((lvl_pts[n_lvl] + lvl_pts[p_lvl] + lvl_pts[k_lvl] + ph_pts) / 4.0, 1)

    issues = []
    if n_lvl == "low":
        issues.append("Low Nitrogen")
    if p_lvl == "low":
        issues.append("Low Phosphorus")
    if k_lvl == "low":
        issues.append("Low Potassium")
    if ph < 6.0 or ph > 7.5:
        issues.append(f"pH Imbalance ({ph_status})")

    verdict = (
        f"Balanced {sample.soil_texture or 'Loamy'} Soil ({ph_status})"
        if not issues
        else f"{', '.join(issues)} — {sample.soil_texture or 'Loamy'} Soil"
    )

    has_numeric = any(v is not None for v in [sample.nitrogen_value, sample.phosphorus_value, sample.potassium_value])
    actions = []
    if not sample.is_validated:
        actions.append("Sample is marked unvalidated — confirm with lab testing before applying specific fertilizer quantities.")
    else:
        if sample.nitrogen_value is not None and sample.nitrogen_value < 20:
            actions.append(f"Apply 40–60 kg/ha Urea (Nitrogen measured at {sample.nitrogen_value} mg/kg).")
        elif n_lvl == "low":
            actions.append("Nitrogen is low; measure exact mg/kg or apply basal organic compost / Urea per local agronomy guide.")
        if sample.phosphorus_value is not None and sample.phosphorus_value < 15:
            actions.append(f"Apply 25–35 kg/ha DAP (Phosphorus measured at {sample.phosphorus_value} mg/kg).")
        elif p_lvl == "low":
            actions.append("Phosphorus is low; consider basal rock phosphate or DAP after quantitative lab check.")
        if sample.potassium_value is not None and sample.potassium_value < 100:
            actions.append(f"Apply 20–30 kg/ha MOP (Potassium measured at {sample.potassium_value} mg/kg).")
        elif k_lvl == "low":
            actions.append("Potassium is low; incorporate potash/wood-ash amendment.")
        if ph < 5.8:
            actions.append("Apply agricultural lime to raise soil pH toward 6.2–7.0.")
        elif ph > 7.8:
            actions.append("Apply gypsum or elemental sulfur with organic matter to moderate alkalinity.")
        if not actions:
            actions.append(
                "Nutrients and pH are within healthy crop ranges. Maintain balanced crop rotation."
                if has_numeric
                else "Qualitative levels look balanced; record numeric lab ppm values for precision dosing."
            )

    top_crops = recommend_crops(
        nitrogen_value=sample.nitrogen_value,
        nitrogen_level=sample.nitrogen_level,
        phosphorus_value=sample.phosphorus_value,
        phosphorus_level=sample.phosphorus_level,
        potassium_value=sample.potassium_value,
        potassium_level=sample.potassium_level,
        ph_value=ph,
        moisture_level=sample.moisture_level or "medium",
        soil_texture=sample.soil_texture or "Loamy",
        is_validated=sample.is_validated,
    )[:3]

    return {
        "fertility_score": fertility_score,
        "verdict": verdict,
        "ph_status": ph_status,
        "nutrient_status": {
            "nitrogen": {"level": n_lvl, "value": sample.nitrogen_value or n_val, "is_measured": sample.nitrogen_value is not None},
            "phosphorus": {"level": p_lvl, "value": sample.phosphorus_value or p_val, "is_measured": sample.phosphorus_value is not None},
            "potassium": {"level": k_lvl, "value": sample.potassium_value or k_val, "is_measured": sample.potassium_value is not None},
        },
        "actions": actions,
        "top_crops": top_crops,
    }
