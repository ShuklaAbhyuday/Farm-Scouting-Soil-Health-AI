"""
Structured Fertilizer Recommendation System combining soil sample nutrients,
crop target demand, field area scaling, and optional optical chlorophyll/moisture proxies.

Scientific Rules:
- Never prescribe numeric fertilizer kg/ha rates without a SoilSample.
- Unvalidated samples receive qualitative nutrient flags only; exact dosages stay locked
  until marked lab/sensor verified (`is_validated=True`).
- When lab-verified (`is_validated=True`), compute per-nutrient rates (kg/ha and total kg
  for `field.area_ha`), split application schedules, DAP starter-N credit, and pH correction.
"""
from __future__ import annotations

from typing import Any, Optional

from backend.services.crop_recommendation_service import _resolve_nutrient

LEGUME_CROPS = {"soybean", "chickpea", "chickpea (gram)", "groundnut", "lentil", "pulses"}
HIGH_N_CROPS = {"maize", "maize (corn)", "rice", "rice (paddy)", "sugarcane"}


def build_fertilizer_plan(
    field_name: str,
    crop_type: Optional[str],
    area_ha: Optional[float],
    soil_sample: Optional[Any],
    ndre_mean: Optional[float] = None,
    ndvi_mean: Optional[float] = None,
    ndmi_mean: Optional[float] = None,
) -> dict[str, Any]:
    """Build a complete stage-wise Fertilizer Recommendation System response."""
    area = float(area_ha) if area_ha and area_ha > 0 else 1.0
    crop_clean = (crop_type or "Wheat").strip()
    crop_key = crop_clean.lower()

    sat_notes: list[str] = []
    if ndre_mean is not None:
        if ndre_mean < 0.25:
            sat_notes.append(f"Satellite NDRE ({ndre_mean:.2f}) indicates lower canopy chlorophyll proxy; split foliar/top-dress N may support uptake if moisture permits.")
        else:
            sat_notes.append(f"Satellite NDRE ({ndre_mean:.2f}) shows healthy chlorophyll signal.")
    if ndmi_mean is not None and ndmi_mean < -0.05:
        sat_notes.append(f"Low canopy moisture proxy (NDMI {ndmi_mean:.2f}): avoid surface Urea spreading on dry soil without irrigation/rain.")

    if soil_sample is None:
        return {
            "status": "soil_sample_required",
            "can_prescribe_dosage": False,
            "is_validated": False,
            "crop_type": crop_clean,
            "area_ha": round(area, 2),
            "summary": "Submit or upload a lab soil test first to unlock tailored N-P-K and pH fertilizer recommendations.",
            "recommendations": [],
            "ph_amendment": None,
            "total_field_materials": [],
            "application_tips": [
                "Satellite sensors detect canopy stress patterns but cannot directly measure soil N, P, K, or pH.",
                "Collect 5–8 representative soil cores (0–15 cm depth) across field zones before purchasing bulk fertilizer.",
            ],
            "satellite_context": sat_notes,
            "limitation": "No soil sample available; prescriptive fertilizer dosages are intentionally withheld to avoid over/under-application.",
        }

    is_validated = bool(soil_sample.is_validated)
    n_val, n_lvl = _resolve_nutrient(soil_sample.nitrogen_value, soil_sample.nitrogen_level, "n")
    p_val, p_lvl = _resolve_nutrient(soil_sample.phosphorus_value, soil_sample.phosphorus_level, "p")
    k_val, k_lvl = _resolve_nutrient(soil_sample.potassium_value, soil_sample.potassium_level, "k")
    ph = float(soil_sample.ph_value) if soil_sample.ph_value is not None else 7.0
    texture = soil_sample.soil_texture or "Loamy"

    # Determine Nitrogen demand modifier by crop family
    if crop_key in LEGUME_CROPS:
        n_factor = 0.45
        n_crop_note = f"{crop_clean} is N-fixing; only starter Nitrogen is recommended."
    elif crop_key in HIGH_N_CROPS:
        n_factor = 1.2
        n_crop_note = f"{crop_clean} has elevated Nitrogen demand; use split top-dressing."
    else:
        n_factor = 1.0
        n_crop_note = f"Standard split-application schedule aligned for {crop_clean}."

    recs: list[dict[str, Any]] = []
    totals: list[dict[str, Any]] = []

    # 1. Phosphorus (DAP 18-46-0) — calculate first so DAP starter N (18%) can be noted
    dap_rate = 0.0
    if p_lvl == "low":
        dap_rate = 35.0 if (soil_sample.phosphorus_value is None or soil_sample.phosphorus_value >= 8) else 45.0
        p_action = "Basal Phosphorus Correction"
        p_priority = "high"
        p_reason = f"Measured/indicated Phosphorus is low ({soil_sample.phosphorus_value or p_lvl}); root establishment and tillering require basal P near seed furrow."
    elif p_lvl == "medium":
        dap_rate = 20.0
        p_action = "Maintenance Phosphorus"
        p_priority = "medium"
        p_reason = f"Phosphorus is moderate ({soil_sample.phosphorus_value or p_lvl}); light basal DAP maintains crop uptake without excess buildup."
    else:
        dap_rate = 0.0
        p_action = "Skip Phosphorus Fertilizer"
        p_priority = "low"
        p_reason = f"Phosphorus is already high ({soil_sample.phosphorus_value or p_lvl}); omit basal DAP this cycle to prevent zinc lockup and runoff."

    # 2. Nitrogen (Urea 46% N) — subtract modest DAP N contribution if DAP applied
    if n_lvl == "low":
        base_urea = 55.0 if (soil_sample.nitrogen_value is None or soil_sample.nitrogen_value >= 12) else 70.0
        n_rate = round(max(15.0, (base_urea * n_factor) - (0.39 * dap_rate)), 1)
        n_priority = "high"
        n_action = "Primary Nitrogen Boost"
        n_reason = f"Nitrogen is low ({soil_sample.nitrogen_value or n_lvl} {'mg/kg' if soil_sample.nitrogen_value else ''}). {n_crop_note}".strip()
    elif n_lvl == "medium":
        n_rate = round(max(0.0, (32.0 * n_factor) - (0.39 * dap_rate)), 1)
        n_priority = "medium"
        n_action = "Balanced Split Nitrogen"
        n_reason = f"Nitrogen is moderate ({soil_sample.nitrogen_value or n_lvl}). {n_crop_note}"
    else:
        n_rate = 0.0
        n_priority = "low"
        n_action = "Hold Bulk Nitrogen"
        n_reason = f"Nitrogen is high ({soil_sample.nitrogen_value or n_lvl}); avoid excess Urea which increases lodging and nitrate leaching."

    # 3. Potassium (MOP 60% K2O)
    if k_lvl == "low":
        k_rate = 30.0 if (soil_sample.potassium_value is None or soil_sample.potassium_value >= 60) else 40.0
        k_priority = "high"
        k_action = "Potash Root & Stress Amendment"
        k_reason = f"Potassium is low ({soil_sample.potassium_value or k_lvl}); MOP improves stalk strength, stomatal water regulation, and grain fill."
    elif k_lvl == "medium":
        k_rate = 15.0
        k_priority = "medium"
        k_action = "Maintenance Potash"
        k_reason = f"Potassium is moderate ({soil_sample.potassium_value or k_lvl}); light basal MOP supports grain quality."
    else:
        k_rate = 0.0
        k_priority = "low"
        k_action = "Skip Potash Fertilizer"
        k_reason = f"Potassium is already sufficient/high ({soil_sample.potassium_value or k_lvl}); no MOP needed."

    # Package per-nutrient cards (withholding exact numbers cleanly when sample is unvalidated)
    nutrient_specs = [
        (
            "Nitrogen (N)",
            "Urea (46-0-0)",
            n_lvl,
            soil_sample.nitrogen_value,
            n_rate,
            "50% basal + 25% at 21–25 DAS + 25% pre-flowering (or foliar spray if irrigated)",
            n_action,
            n_priority,
            n_reason,
        ),
        (
            "Phosphorus (P)",
            "DAP (18-46-0)",
            p_lvl,
            soil_sample.phosphorus_value,
            dap_rate,
            "100% basal banded 3–5 cm below/beside seed at sowing",
            p_action,
            p_priority,
            p_reason,
        ),
        (
            "Potassium (K)",
            "MOP / Muriate of Potash (0-0-60)",
            k_lvl,
            soil_sample.potassium_value,
            k_rate,
            "100% basal incorporated before sowing (split 50/50 on light Sandy soils)" if "sandy" in texture.lower() else "100% basal incorporated during final land preparation",
            k_action,
            k_priority,
            k_reason,
        ),
    ]

    for nutrient, product, lvl, raw_val, rate_kg_ha, timing, action, priority, reason in nutrient_specs:
        total_kg = round(rate_kg_ha * area, 1) if is_validated and rate_kg_ha > 0 else None
        recs.append({
            "nutrient": nutrient,
            "product": product,
            "soil_level": lvl,
            "measured_mg_kg": raw_val,
            "action": action,
            "priority": priority,
            "rate_kg_ha": rate_kg_ha if is_validated else None,
            "total_field_kg": total_kg,
            "timing": timing,
            "reasoning": reason,
        })
        if is_validated and rate_kg_ha > 0 and total_kg is not None:
            totals.append({
                "product": product,
                "rate_kg_ha": rate_kg_ha,
                "total_kg": total_kg,
                "bags_50kg": round(total_kg / 50.0, 1),
            })

    # 4. pH Amendment check
    ph_amendment = None
    if ph < 5.8:
        lime_rate = 300.0 if ph >= 5.2 else 500.0
        ph_amendment = {
            "status": "acidic_correction_needed",
            "title": f"Apply Agricultural Lime (Current pH {ph})",
            "rate_kg_ha": lime_rate if is_validated else None,
            "total_field_kg": round(lime_rate * area, 1) if is_validated else None,
            "timing": "Incorporate 2–4 weeks prior to sowing",
            "reasoning": "Low soil pH limits Phosphorus availability and increases aluminum/manganese toxicity; correct pH before heavy NPK applications.",
        }
    elif ph > 7.8:
        gyp_rate = 250.0 if ph <= 8.4 else 450.0
        ph_amendment = {
            "status": "alkaline_correction_needed",
            "title": f"Apply Gypsum / Elemental Sulfur + Compost (Current pH {ph})",
            "rate_kg_ha": gyp_rate if is_validated else None,
            "total_field_kg": round(gyp_rate * area, 1) if is_validated else None,
            "timing": "Broadcast and incorporate with organic matter before pre-sowing irrigation",
            "reasoning": "High pH reduces Phosphorus and micronutrient (Zn, Fe) solubility; gypsum and organic matter buffer root-zone pH.",
        }

    tips = [
        f"Field scaling computed for {round(area, 2)} ha ({crop_clean}, {texture} soil).",
        "Avoid top-dressing Urea right before heavy rainfall or onto dry un-irrigated soil to minimize volatilization and leaching.",
    ]
    if "sandy" in texture.lower():
        tips.append("Sandy texture loses N & K faster to leaching; prefer smaller, more frequent split doses.")
    if ph_amendment:
        tips.append(ph_amendment["reasoning"])

    status = "lab_verified_plan" if is_validated else "unvalidated_estimate"
    summary = (
        f"Tailored NPK & amendment schedule for {crop_clean} across {round(area, 2)} ha based on verified soil sample."
        if is_validated
        else "Preliminary nutrient balance shown below — mark this soil sample as Lab/Sensor Verified to unlock exact kg/ha dosages."
    )

    return {
        "status": status,
        "can_prescribe_dosage": is_validated,
        "is_validated": is_validated,
        "sample_id": soil_sample.id,
        "sample_source": soil_sample.source,
        "crop_type": crop_clean,
        "area_ha": round(area, 2),
        "soil_texture": texture,
        "ph_value": ph,
        "summary": summary,
        "recommendations": recs,
        "ph_amendment": ph_amendment,
        "total_field_materials": totals,
        "application_tips": tips,
        "satellite_context": sat_notes,
        "limitation": (
            "Dosage bands provide initial agronomic guidance normalized for field area and crop class; "
            "adjust with local extension agronomist norms for cultivar yield target, organic carbon, and micronutrients (Zn, B, S)."
        ),
    }
