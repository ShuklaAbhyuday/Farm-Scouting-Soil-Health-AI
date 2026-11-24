import os

services_dir = r"c:\Users\abhyu\OneDrive\Desktop\EPICS\backend\services"
os.makedirs(services_dir, exist_ok=True)

files = {
    "__init__.py": "",
    "gee_service.py": '''import ee
import numpy as np
from backend.config import settings
import json, base64, logging
import random
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class GEEService:
    def __init__(self):
        self._initialized = False
    
    def initialize(self):
        """Initialize GEE. Uses service account if available, else interactive auth."""
        if self._initialized:
            return True
        try:
            if settings.GEE_SERVICE_ACCOUNT_KEY_PATH:
                credentials = ee.ServiceAccountCredentials(
                    email=None,
                    key_file=settings.GEE_SERVICE_ACCOUNT_KEY_PATH
                )
                ee.Initialize(credentials, project=settings.GEE_PROJECT_ID)
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
        """Query Sentinel-2 SR Harmonized collection."""
        collection = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
            .filterBounds(geometry)
            .filterDate(start_date, end_date)
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', cloud_max)))
        return collection
    
    def mask_clouds(self, image):
        """Mask clouds using SCL band."""
        scl = image.select('SCL')
        mask = (scl.neq(3)  # cloud shadow
               .And(scl.neq(8))  # cloud medium prob
               .And(scl.neq(9))  # cloud high prob
               .And(scl.neq(10)))  # cirrus
        return image.updateMask(mask).divide(10000)  # Scale to 0-1 reflectance
    
    def calculate_indices(self, image):
        """Calculate NDVI, NDMI, NDRE from Sentinel-2 bands."""
        ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
        ndmi = image.normalizedDifference(['B8', 'B11']).rename('NDMI')
        ndre = image.normalizedDifference(['B8', 'B5']).rename('NDRE')
        return image.addBands([ndvi, ndmi, ndre])
    
    def analyze_field(self, boundary_geojson, start_date, end_date, cloud_max=20):
        """Full pipeline: query → mask → indices → statistics."""
        # Convert boundary
        import geojson
        geom = geojson.loads(boundary_geojson)
        ee_geom = ee.Geometry(geom)
        
        col = self.get_sentinel2_collection(ee_geom, start_date, end_date, cloud_max)
        if col.size().getInfo() == 0:
            return None
        
        # Take the most recent image
        image = col.sort('system:time_start', False).first()
        image = self.mask_clouds(image)
        image = self.calculate_indices(image)
        
        return {
            'ndvi_stats': self.get_index_stats(image, ee_geom, 'NDVI'),
            'ndmi_stats': self.get_index_stats(image, ee_geom, 'NDMI'),
            'ndre_stats': self.get_index_stats(image, ee_geom, 'NDRE'),
            'cloud_cover': image.get('CLOUDY_PIXEL_PERCENTAGE').getInfo(),
            'acquisition_date': datetime.fromtimestamp(image.get('system:time_start').getInfo() / 1000.0)
        }
    
    def get_tile_url(self, image, vis_params):
        """Get tile URL for map display."""
        map_id = image.getMapId(vis_params)
        return map_id['tile_fetcher'].url_format
    
    def get_index_stats(self, image, geometry, index_name):
        """Get statistics for an index within a geometry."""
        stats = image.select(index_name).reduceRegion(
            reducer=ee.Reducer.mean().combine(ee.Reducer.minMax(), sharedInputs=True)
                .combine(ee.Reducer.stdDev(), sharedInputs=True),
            geometry=geometry,
            scale=10,
            maxPixels=1e9
        ).getInfo()
        return stats
    
    def get_pixel_values(self, image, geometry, index_name, scale=10):
        """Get array of pixel values for ML processing."""
        return np.array([]) # Placeholder for actual implementation

class DemoGEEService:
    def __init__(self):
        self._initialized = True
        logger.info("[DEMO] Simulated Demo GEE Service initialized")

    def initialize(self):
        return True

    def analyze_field(self, boundary_geojson, start_date, end_date, cloud_max=20):
        """Simulate [DEMO] data — not from actual satellite imagery"""
        logger.info("[DEMO] Generating simulated data — not from actual satellite imagery")
        
        # realistic NDVI (0.2-0.85)
        ndvi_mean = random.uniform(0.5, 0.8)
        
        return {
            'ndvi_stats': {'NDVI_mean': ndvi_mean, 'NDVI_min': ndvi_mean - 0.2, 'NDVI_max': ndvi_mean + 0.1, 'NDVI_stdDev': 0.05},
            'ndmi_stats': {'NDMI_mean': ndvi_mean - 0.1, 'NDMI_min': ndvi_mean - 0.3, 'NDMI_max': ndvi_mean + 0.1, 'NDMI_stdDev': 0.04},
            'ndre_stats': {'NDRE_mean': ndvi_mean - 0.2, 'NDRE_min': ndvi_mean - 0.4, 'NDRE_max': ndvi_mean, 'NDRE_stdDev': 0.06},
            'cloud_cover': random.uniform(0, 10),
            'acquisition_date': datetime.utcnow() - timedelta(days=random.randint(1, 5)),
            'demo_warning': "[DEMO] Simulated data — not from actual satellite imagery"
        }
    
    def get_tile_url(self, image, vis_params):
        return "https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}"
        
def get_gee_service():
    if settings.DEMO_MODE:
        return DemoGEEService()
    return GEEService()
''',
    "index_calculator.py": '''import numpy as np

class IndexCalculator:
    """Calculates indices from raw band arrays (numpy) avoiding division by zero."""
    
    @staticmethod
    def calculate_ndvi(nir, red):
        """NDVI = (NIR - Red) / (NIR + Red)"""
        numerator = nir - red
        denominator = nir + red
        return np.divide(numerator, denominator, out=np.zeros_like(numerator), where=denominator!=0)
        
    @staticmethod
    def calculate_ndmi(nir, swir):
        """NDMI = (NIR - SWIR) / (NIR + SWIR)"""
        numerator = nir - swir
        denominator = nir + swir
        return np.divide(numerator, denominator, out=np.zeros_like(numerator), where=denominator!=0)
        
    @staticmethod
    def calculate_ndre(nir, red_edge):
        """NDRE = (NIR - RedEdge) / (NIR + RedEdge)"""
        numerator = nir - red_edge
        denominator = nir + red_edge
        return np.divide(numerator, denominator, out=np.zeros_like(numerator), where=denominator!=0)
''',
    "hotspot_service.py": '''import numpy as np
from backend.config import settings

class HotspotService:
    def __init__(self):
        pass

    def detect_hotspots_baseline(self, ndvi_array, ndmi_array, ndre_array, temporal_deviation=None):
        """
        BASELINE HEURISTIC anomaly detector.
        This is NOT an AI/ML model — it's a simple weighted scoring formula.
        Used as the default detection method.
        """
        if temporal_deviation is None:
            temporal_deviation = np.zeros_like(ndvi_array)
            
        w1, w2, w3, w4 = settings.NDVI_WEIGHT, settings.NDMI_WEIGHT, settings.NDRE_WEIGHT, settings.TEMPORAL_WEIGHT
        
        # Normalize arrays 0-1 assuming ranges (NDVI 0-1, NDMI -1 to 1, etc. Just scaling roughly for heuristic)
        norm_ndvi = np.clip(ndvi_array, 0, 1)
        norm_ndmi = np.clip((ndmi_array + 1) / 2, 0, 1)
        norm_ndre = np.clip(ndre_array, 0, 1)
        
        health_score = (
            w1 * norm_ndvi +
            w2 * norm_ndmi +
            w3 * norm_ndre -
            w4 * np.abs(temporal_deviation)
        )
        
        # Scale to 0-100
        health_score_100 = health_score * 100
        return health_score_100

    def detect_hotspots_ml(self, feature_matrix):
        """
        ML-based anomaly detection using Isolation Forest (scikit-learn).
        This is the actual AI/ML model for the project.
        Requires sufficient data points to be meaningful.
        """
        from sklearn.ensemble import IsolationForest
        clf = IsolationForest(contamination=0.1, random_state=42)
        preds = clf.fit_predict(feature_matrix)
        # -1 indicates anomaly, 1 indicates normal
        return preds
''',
    "recommendation_service.py": '''from backend.models.soil_sample import SoilSample
import json

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
''',
    "report_service.py": '''from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import os

class ReportService:
    def generate_pdf_report(self, field, observations, recommendations, file_path):
        """
        Generate PDF report using ReportLab.
        Clear labeling: "Satellite-Derived" vs "Ground-Truth".
        """
        c = canvas.Canvas(file_path, pagesize=letter)
        c.drawString(100, 750, f"Farm Scouting Report - Field: {field.name}")
        c.drawString(100, 730, "===============================================")
        
        y = 700
        c.drawString(100, y, "--- Satellite-Derived Data ---")
        y -= 20
        for obs in observations:
            c.drawString(100, y, f"Date: {obs.acquisition_date} | Cloud: {obs.cloud_cover_pct}%")
            y -= 20
            
        y -= 20
        c.drawString(100, y, "--- Ground-Truth Data & Recommendations ---")
        y -= 20
        for rec in recommendations:
            c.drawString(100, y, f"[{rec.category.upper()}] {rec.title}")
            y -= 20
            c.drawString(120, y, f"Reasoning: {rec.reasoning}")
            y -= 30
            
        c.save()
        return file_path
'''
}

for filename, content in files.items():
    with open(os.path.join(services_dir, filename), "w", encoding='utf-8') as f:
        f.write(content)
