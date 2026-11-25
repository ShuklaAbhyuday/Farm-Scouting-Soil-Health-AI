import ee
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
        import geojson
        geom = geojson.loads(boundary_geojson)
        ee_geom = ee.Geometry(geom)
        
        col = self.get_sentinel2_collection(ee_geom, start_date, end_date, cloud_max)
        if col.size().getInfo() == 0:
            return None
        
        raw_image = col.sort('system:time_start', False).first()
        time_start = raw_image.get('system:time_start').getInfo()
        cloud_pct = raw_image.get('CLOUDY_PIXEL_PERCENTAGE').getInfo()

        image = self.calculate_indices(self.mask_clouds(raw_image))
        ndvi_stats = self.get_index_stats(image, ee_geom, 'NDVI')

        # If the single latest scene had clouds over the exact polygon, fall back to a cloud-masked median composite
        if not ndvi_stats or ndvi_stats.get('NDVI_mean') is None:
            composite = col.map(self.mask_clouds).median()
            image = self.calculate_indices(composite)
            ndvi_stats = self.get_index_stats(image, ee_geom, 'NDVI')

        if not ndvi_stats or ndvi_stats.get('NDVI_mean') is None:
            return None

        return {
            'ndvi_stats': ndvi_stats,
            'ndmi_stats': self.get_index_stats(image, ee_geom, 'NDMI'),
            'ndre_stats': self.get_index_stats(image, ee_geom, 'NDRE'),
            'cloud_cover': cloud_pct if cloud_pct is not None else 0.0,
            'acquisition_date': datetime.fromtimestamp(time_start / 1000.0) if time_start else datetime.utcnow()
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
        return np.array([]) 

class DemoGEEService:
    def __init__(self):
        self._initialized = True
        logger.info("[DEMO] Simulated Demo GEE Service initialized")

    def initialize(self):
        return True

    def analyze_field(self, boundary_geojson, start_date, end_date, cloud_max=20):
        """Simulate [DEMO] data — not from actual satellite imagery"""
        logger.info("[DEMO] Generating simulated data — not from actual satellite imagery")
        
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
