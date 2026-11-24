import json


class RecommendationService:
    def generate_recommendation(self, field_id, soil_samples, satellite_data, hotspot_id=None):
        """
        CRITICAL RULES:
        - If ground_truth soil data exists AND is_validated=True AND has numeric values -> specific fertilizer category + approximate range
        - If ground_truth exists but is_validated=False (or lacks numeric values) -> general guidance + "Recommend validating soil data with lab testing"
        - If NO ground truth -> NEVER provide fertilizer quantities. Say: "Ground soil testing recommended before fertilizer application. Satellite data indicates [stress type] but cannot determine specific nutrient levels."
        - ALWAYS include reasoning field.
        """
        recommendations = []
        sat_evidence = json.dumps(satellite_data)
        ndvi_mean = satellite_data.get("NDVI_mean", 0.65)
        ndmi_mean = satellite_data.get("NDMI_mean", 0.2)
        ndre_mean = satellite_data.get("NDRE_mean", 0.4)

        stress_type = "mild canopy variation"
        if ndmi_mean < 0.0:
            stress_type = "moisture / water stress"
        elif ndre_mean < 0.3:
            stress_type = "chlorophyll / nitrogen-proxy stress"
        elif ndvi_mean < 0.5:
            stress_type = "low vegetative vigor"

        if not soil_samples:
            recommendations.append({
                "category": "fertilizer",
                "title": "Ground soil testing required before application",
                "description": (
                    f"Ground soil testing recommended before fertilizer application. "
                    f"Satellite data indicates {stress_type} (NDVI {ndvi_mean:.2f}, NDRE {ndre_mean:.2f}) "
                    f"but cannot determine specific nutrient levels."
                ),
                "reasoning": "Satellite imagery (NDVI/NDRE) shows spatial stress patterns, but optical sensors do NOT measure soil N, P, K, or pH directly.",
                "satellite_evidence": sat_evidence,
                "ground_truth_evidence": None,
                "confidence": "low",
                "priority": "high" if ndvi_mean < 0.55 else "medium",
                "requires_ground_truth": True,
            })
        else:
            valid_samples = [s for s in soil_samples if s.is_validated]
            unvalid_samples = [s for s in soil_samples if not s.is_validated]

            if valid_samples:
                s = valid_samples[0]
                gt_evidence = json.dumps({
                    "N": s.nitrogen_value or s.nitrogen_level,
                    "P": s.phosphorus_value or s.phosphorus_level,
                    "K": s.potassium_value or s.potassium_level,
                    "pH": s.ph_value,
                })

                has_numeric = any(v is not None for v in [s.nitrogen_value, s.phosphorus_value, s.potassium_value])

                if s.nitrogen_value is not None and s.nitrogen_value < 20:
                    recommendations.append({
                        "category": "fertilizer",
                        "title": "Apply Nitrogen Fertilizer (Urea)",
                        "description": f"Apply 40-60 kg/ha of Urea (measured available N: {s.nitrogen_value} mg/kg, NDRE: {ndre_mean:.2f}).",
                        "reasoning": "Validated lab/sensor soil data confirms low Nitrogen combined with reduced NDRE chlorophyll signal.",
                        "satellite_evidence": sat_evidence,
                        "ground_truth_evidence": gt_evidence,
                        "confidence": "high",
                        "priority": "high",
                        "requires_ground_truth": False,
                    })
                elif s.nitrogen_level == "low":
                    recommendations.append({
                        "category": "fertilizer",
                        "title": "Nitrogen Supplementation Recommended",
                        "description": "Validated qualitative sample shows Low Nitrogen. Confirm exact kg/ha dosage with quantitative lab ppm readout before bulk spreading.",
                        "reasoning": "Sample is validated with qualitative 'low' rating without numeric ppm value.",
                        "satellite_evidence": sat_evidence,
                        "ground_truth_evidence": gt_evidence,
                        "confidence": "medium",
                        "priority": "high",
                        "requires_ground_truth": not has_numeric,
                    })

                if s.phosphorus_value is not None and s.phosphorus_value < 15:
                    recommendations.append({
                        "category": "fertilizer",
                        "title": "Apply Phosphorus Fertilizer (DAP)",
                        "description": f"Apply 25-35 kg/ha of DAP (measured P: {s.phosphorus_value} mg/kg).",
                        "reasoning": "Validated ground-truth sample shows Phosphorus deficiency.",
                        "satellite_evidence": sat_evidence,
                        "ground_truth_evidence": gt_evidence,
                        "confidence": "high",
                        "priority": "medium",
                        "requires_ground_truth": False,
                    })
                elif s.phosphorus_level == "low":
                    recommendations.append({
                        "category": "fertilizer",
                        "title": "Phosphorus Deficiency Flagged",
                        "description": "Validated soil test notes Low Phosphorus. Consider basal P amendment after quantitative confirmation.",
                        "reasoning": "Qualitative Phosphorus marked low.",
                        "satellite_evidence": sat_evidence,
                        "ground_truth_evidence": gt_evidence,
                        "confidence": "medium",
                        "priority": "medium",
                        "requires_ground_truth": not has_numeric,
                    })

                if s.potassium_value is not None and s.potassium_value < 100:
                    recommendations.append({
                        "category": "fertilizer",
                        "title": "Apply Potassium Fertilizer (MOP)",
                        "description": f"Apply 20-30 kg/ha of Muriate of Potash (measured K: {s.potassium_value} mg/kg).",
                        "reasoning": "Validated ground-truth sample shows low Potassium.",
                        "satellite_evidence": sat_evidence,
                        "ground_truth_evidence": gt_evidence,
                        "confidence": "high",
                        "priority": "medium",
                        "requires_ground_truth": False,
                    })

                if s.ph_value is not None and (s.ph_value < 5.8 or s.ph_value > 7.8):
                    amendment = "agricultural lime" if s.ph_value < 5.8 else "gypsum / elemental sulfur"
                    recommendations.append({
                        "category": "soil",
                        "title": f"Soil pH Adjustment Needed (pH {s.ph_value})",
                        "description": f"Soil pH ({s.ph_value}) is outside optimal crop range (6.0-7.5). Consider {amendment} to improve nutrient uptake.",
                        "reasoning": "Extreme pH locks out NPK nutrients even when present in soil.",
                        "satellite_evidence": sat_evidence,
                        "ground_truth_evidence": gt_evidence,
                        "confidence": "high",
                        "priority": "high",
                        "requires_ground_truth": False,
                    })

                if not recommendations:
                    recommendations.append({
                        "category": "crop",
                        "title": "Maintain Current Nutrient Schedule",
                        "description": f"Validated soil nutrients (N: {s.nitrogen_level}, pH: {s.ph_value}) are balanced. Continue routine monitoring.",
                        "reasoning": "No severe nutrient deficiency detected in validated ground-truth samples.",
                        "satellite_evidence": sat_evidence,
                        "ground_truth_evidence": gt_evidence,
                        "confidence": "high",
                        "priority": "low",
                        "requires_ground_truth": False,
                    })
            elif unvalid_samples:
                s = unvalid_samples[0]
                gt_evidence = json.dumps({"N": s.nitrogen_level, "P": s.phosphorus_level, "K": s.potassium_level, "pH": s.ph_value})
                recommendations.append({
                    "category": "fertilizer",
                    "title": "Validate Unverified Soil Data",
                    "description": (
                        f"Unvalidated {s.source} entry reports N={s.nitrogen_level}, pH={s.ph_value}. "
                        f"Recommend validating soil data with lab testing before fertilizer application."
                    ),
                    "reasoning": "Ground truth exists but is marked unvalidated; exact dosages require verified lab numbers.",
                    "satellite_evidence": sat_evidence,
                    "ground_truth_evidence": gt_evidence,
                    "confidence": "medium",
                    "priority": "medium",
                    "requires_ground_truth": True,
                })

        if ndmi_mean < 0.05:
            recommendations.append({
                "category": "irrigation",
                "title": "Schedule Targeted Irrigation",
                "description": f"Check soil moisture and schedule irrigation in stressed zones (NDMI mean: {ndmi_mean:.2f}).",
                "reasoning": f"NDMI ({ndmi_mean:.2f}) indicates low canopy water content / early water stress.",
                "satellite_evidence": sat_evidence,
                "ground_truth_evidence": None,
                "confidence": "high",
                "priority": "critical" if ndmi_mean < 0 else "high",
                "requires_ground_truth": False,
            })

        return recommendations
