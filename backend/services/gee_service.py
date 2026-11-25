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
    
    def analyze_field(self, boundary_geojson, start_date, end_date, cloud_max=20, zone_geoms=None):
        """Full pipeline: query → mask → indices → single-batch field & per-zone statistics."""
        import geojson
        geom = geojson.loads(boundary_geojson)
        ee_geom = ee.Geometry(geom)

        col = self.get_sentinel2_collection(ee_geom, start_date, end_date, cloud_max)
        raw_image = col.sort('system:time_start', False).first()
        if raw_image is None:
            return None

        try:
            meta = raw_image.toDictionary(['system:time_start', 'CLOUDY_PIXEL_PERCENTAGE']).getInfo()
        except Exception:
            return None
        if not meta:
            return None

        time_start = meta.get('system:time_start')
        cloud_pct = meta.get('CLOUDY_PIXEL_PERCENTAGE')

        image = self.calculate_indices(self.mask_clouds(raw_image)).select(['NDVI', 'NDMI', 'NDRE'])
        reducer = (
            ee.Reducer.mean()
            .combine(ee.Reducer.minMax(), sharedInputs=True)
            .combine(ee.Reducer.stdDev(), sharedInputs=True)
        )
        stats = image.reduceRegion(
            reducer=reducer,
            geometry=ee_geom,
            scale=20,
            maxPixels=1e9,
            bestEffort=True,
        ).getInfo()

        if not stats or stats.get('NDVI_mean') is None:
            composite = col.map(self.mask_clouds).median()
            image = self.calculate_indices(composite).select(['NDVI', 'NDMI', 'NDRE'])
            stats = image.reduceRegion(
                reducer=reducer,
                geometry=ee_geom,
                scale=20,
                maxPixels=1e9,
                bestEffort=True,
            ).getInfo()

        if not stats or stats.get('NDVI_mean') is None:
            return None

        # Fetch REAL per-zone statistics in a single batch reduceRegions call
        zone_stats = {}
        if zone_geoms:
            features = [
                ee.Feature(ee.Geometry(z_geo), {'cell_idx': idx})
                for idx, z_geo in enumerate(zone_geoms)
            ]
            fc = ee.FeatureCollection(features)
            rr = image.reduceRegions(
                collection=fc,
                reducer=ee.Reducer.mean(),
                scale=10,
            ).getInfo()

            for feat in rr.get('features', []):
                props = feat.get('properties', {})
                c_idx = props.get('cell_idx')
                if c_idx is not None and props.get('NDVI') is not None:
                    zone_stats[int(c_idx)] = {
                        'NDVI': float(props.get('NDVI')),
                        'NDMI': float(props.get('NDMI') if props.get('NDMI') is not None else stats.get('NDMI_mean', 0.0)),
                        'NDRE': float(props.get('NDRE') if props.get('NDRE') is not None else stats.get('NDRE_mean', 0.0)),
                    }

            # Fill any individually cloud-masked sub-cells from cloud-masked median composite
            if len(zone_stats) < len(zone_geoms):
                missing = [
                    ee.Feature(ee.Geometry(zone_geoms[idx]), {'cell_idx': idx})
                    for idx in range(len(zone_geoms))
                    if idx not in zone_stats
                ]
                if missing:
                    comp_img = self.calculate_indices(col.map(self.mask_clouds).median()).select(['NDVI', 'NDMI', 'NDRE'])
                    rr_comp = comp_img.reduceRegions(
                        collection=ee.FeatureCollection(missing),
                        reducer=ee.Reducer.mean(),
                        scale=10,
                    ).getInfo()
                    for feat in rr_comp.get('features', []):
                        props = feat.get('properties', {})
                        c_idx = props.get('cell_idx')
                        if c_idx is not None and props.get('NDVI') is not None:
                            zone_stats[int(c_idx)] = {
                                'NDVI': float(props.get('NDVI')),
                                'NDMI': float(props.get('NDMI') if props.get('NDMI') is not None else stats.get('NDMI_mean', 0.0)),
                                'NDRE': float(props.get('NDRE') if props.get('NDRE') is not None else stats.get('NDRE_mean', 0.0)),
                            }

        return {
            'ndvi_stats': {
                'NDVI_mean': stats.get('NDVI_mean', 0.0),
                'NDVI_min': stats.get('NDVI_min', 0.0),
                'NDVI_max': stats.get('NDVI_max', 0.0),
                'NDVI_stdDev': stats.get('NDVI_stdDev', 0.0),
            },
            'ndmi_stats': {
                'NDMI_mean': stats.get('NDMI_mean', 0.0),
                'NDMI_min': stats.get('NDMI_min', 0.0),
                'NDMI_max': stats.get('NDMI_max', 0.0),
                'NDMI_stdDev': stats.get('NDMI_stdDev', 0.0),
            },
            'ndre_stats': {
                'NDRE_mean': stats.get('NDRE_mean', 0.0),
                'NDRE_min': stats.get('NDRE_min', 0.0),
                'NDRE_max': stats.get('NDRE_max', 0.0),
                'NDRE_stdDev': stats.get('NDRE_stdDev', 0.0),
            },
            'zone_stats': zone_stats,
            'is_demo': False,
            'cloud_cover': cloud_pct if cloud_pct is not None else 0.0,
            'acquisition_date': datetime.fromtimestamp(time_start / 1000.0) if time_start else datetime.utcnow(),
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

    def analyze_field(self, boundary_geojson, start_date, end_date, cloud_max=20, zone_geoms=None):
        """Simulate [DEMO] data — not from actual satellite imagery"""
        logger.info("[DEMO] Generating simulated data — not from actual satellite imagery")
        
        ndvi_mean = random.uniform(0.5, 0.8)
        ndmi_mean = ndvi_mean - 0.1
        ndre_mean = ndvi_mean - 0.2

        zone_stats = {}
        if zone_geoms:
            for idx in range(len(zone_geoms)):
                if idx in (2, 5, 10) and len(zone_geoms) > 2:
                    zone_stats[idx] = {
                        'NDVI': max(0.15, ndvi_mean - random.uniform(0.22, 0.35)),
                        'NDMI': max(-0.4, ndmi_mean - random.uniform(0.20, 0.30)),
                        'NDRE': max(0.10, ndre_mean - random.uniform(0.15, 0.25)),
                    }
                else:
                    zone_stats[idx] = {
                        'NDVI': min(0.95, max(0.2, ndvi_mean + random.uniform(-0.06, 0.07))),
                        'NDMI': min(0.8, max(-0.3, ndmi_mean + random.uniform(-0.05, 0.05))),
                        'NDRE': min(0.85, max(0.1, ndre_mean + random.uniform(-0.05, 0.05))),
                    }

        return {
            'ndvi_stats': {'NDVI_mean': ndvi_mean, 'NDVI_min': ndvi_mean - 0.2, 'NDVI_max': ndvi_mean + 0.1, 'NDVI_stdDev': 0.05},
            'ndmi_stats': {'NDMI_mean': ndmi_mean, 'NDMI_min': ndmi_mean - 0.2, 'NDMI_max': ndmi_mean + 0.2, 'NDMI_stdDev': 0.04},
            'ndre_stats': {'NDRE_mean': ndre_mean, 'NDRE_min': ndre_mean - 0.2, 'NDRE_max': ndre_mean + 0.2, 'NDRE_stdDev': 0.06},
            'zone_stats': zone_stats,
            'is_demo': True,
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
