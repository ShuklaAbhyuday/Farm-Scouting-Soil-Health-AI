import json
from backend.models.soil_sample import SoilSample

class RecommendationService:
    def generate_recommendation(self, field_id, soil_samples, satellite_data, hotspot_id=None):
        """
        CRITICAL RULES:
        - If ground_truth soil data exists AND is_validated=True AND has numeric values -> specific fertilizer category + approximate range
        - If ground_truth exists but is_validated=False -> general guidance + "Recommend validating soil data with lab testing"
        - If NO ground truth -> NEVER provide fertilizer quantities. Say: "Ground soil testing recommended before fertilizer application. Satellite data indicates [stress type] but cannot determine specific nutrient levels."
        - ALWAYS include reasoning field.
        """
        recommendations = []
        
        sat_evidence = json.dumps(satellite_data)
        
        if not soil_samples:
            recommendations.append({
                "category": "fertilizer",
                "title": "Ground testing required",
                "description": "Ground soil testing recommended before fertilizer application. Satellite data indicates stress but cannot determine specific nutrient levels.",
                "reasoning": "Satellite imagery (NDVI/NDRE) shows low vigor, but it does NOT measure NPK directly.",
                "satellite_evidence": sat_evidence,
                "ground_truth_evidence": None,
                "confidence": "low",
                "priority": "medium",
                "requires_ground_truth": True
            })
            return recommendations
            
        valid_samples = [s for s in soil_samples if s.is_validated]
        unvalid_samples = [s for s in soil_samples if not s.is_validated]
        
        if valid_samples:
            s = valid_samples[0]
            gt_evidence = json.dumps({"N": s.nitrogen_value, "P": s.phosphorus_value, "K": s.potassium_value})
            if s.nitrogen_value and s.nitrogen_value < 20:
                recommendations.append({
                    "category": "fertilizer",
                    "title": "Apply Nitrogen Fertilizer",
                    "description": "Apply 40-60 kg/ha of Urea.",
                    "reasoning": "Validated ground-truth agronomic data shows low Nitrogen levels.",
                    "satellite_evidence": sat_evidence,
                    "ground_truth_evidence": gt_evidence,
                    "confidence": "high",
                    "priority": "high",
                    "requires_ground_truth": False
                })
        elif unvalid_samples:
            s = unvalid_samples[0]
            gt_evidence = json.dumps({"N": s.nitrogen_level})
            recommendations.append({
                "category": "fertilizer",
                "title": "Validate Soil Data",
                "description": f"Sensor/manual data suggests {s.nitrogen_level} Nitrogen. Recommend validating soil data with lab testing before application.",
                "reasoning": "Ground truth exists but is not validated lab data.",
                "satellite_evidence": sat_evidence,
                "ground_truth_evidence": gt_evidence,
                "confidence": "medium",
                "priority": "medium",
                "requires_ground_truth": True
            })
            
        # Irrigation recommendation based on NDMI
        ndmi_mean = satellite_data.get('NDMI_mean', 0)
        if ndmi_mean < 0:
            recommendations.append({
                "category": "irrigation",
                "title": "Increase Irrigation",
                "description": "Increase irrigation in affected zones.",
                "reasoning": f"NDMI value ({ndmi_mean}) is negative, indicating water stress.",
                "satellite_evidence": sat_evidence,
                "ground_truth_evidence": None,
                "confidence": "high",
                "priority": "critical",
                "requires_ground_truth": False
            })
            
        return recommendations
