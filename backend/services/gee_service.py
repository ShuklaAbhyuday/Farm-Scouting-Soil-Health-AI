import ee
import numpy as np
from backend.config import settings
import json, base64, logging
import random
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

OPTICAL_BANDS = ['NDVI', 'EVI', 'SAVI', 'GNDVI', 'NDMI', 'NDRE']


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
        return (
            ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
            .filterBounds(geometry)
            .filterDate(start_date, end_date)
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', cloud_max))
        )

    def mask_clouds(self, image):
        """Mask clouds using SCL band and scale reflectance to 0-1."""
        scl = image.select('SCL')
        mask = (
            scl.neq(3)
            .And(scl.neq(8))
            .And(scl.neq(9))
            .And(scl.neq(10))
        )
        return image.updateMask(mask).divide(10000).copyProperties(image, ['system:time_start', 'CLOUDY_PIXEL_PERCENTAGE'])

    def calculate_indices(self, image):
        """Calculate NDVI, EVI, SAVI, GNDVI, NDMI, and NDRE from Sentinel-2 bands."""
        ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
        ndmi = image.normalizedDifference(['B8', 'B11']).rename('NDMI')
        ndre = image.normalizedDifference(['B8', 'B5']).rename('NDRE')
        gndvi = image.normalizedDifference(['B8', 'B3']).rename('GNDVI')
        savi = image.expression(
            '1.5 * (NIR - RED) / (NIR + RED + 0.5)',
            {'NIR': image.select('B8'), 'RED': image.select('B4')},
        ).clamp(-1, 1.5).rename('SAVI')
        evi = image.expression(
            '2.5 * (NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1)',
            {'NIR': image.select('B8'), 'RED': image.select('B4'), 'BLUE': image.select('B2')},
        ).clamp(-1, 1.5).rename('EVI')
        return image.addBands([ndvi, evi, savi, gndvi, ndmi, ndre])

    def _get_sentinel1_stats(self, ee_geom, end_date):
        """Fetch cloud-independent Sentinel-1 SAR GRD VV/VH backscatter and Radar Vegetation Index."""
        try:
            end_dt = datetime.strptime(end_date[:10], '%Y-%m-%d')
        except Exception:
            end_dt = datetime.utcnow()
        start_s1 = (end_dt - timedelta(days=60)).strftime('%Y-%m-%d')
        end_s1 = (end_dt + timedelta(days=1)).strftime('%Y-%m-%d')

        try:
            s1_col = (
                ee.ImageCollection('COPERNICUS/S1_GRD')
                .filterBounds(ee_geom)
                .filterDate(start_s1, end_s1)
                .filter(ee.Filter.eq('instrumentMode', 'IW'))
                .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
                .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'))
                .sort('system:time_start', False)
            )
            s1_img = s1_col.first()
            meta = s1_img.toDictionary(['system:time_start']).getInfo()
            if not meta:
                return None

            vv_lin = ee.Image(10).pow(s1_img.select('VV').divide(10))
            vh_lin = ee.Image(10).pow(s1_img.select('VH').divide(10))
            rvi = vh_lin.multiply(4).divide(vv_lin.add(vh_lin)).clamp(0, 1).rename('S1_RVI')
            combined = s1_img.select(['VV', 'VH']).addBands(rvi)

            s1_vals = combined.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=ee_geom,
                scale=10,
                maxPixels=1e8,
                bestEffort=True,
            ).getInfo()

            if not s1_vals or s1_vals.get('VV') is None:
                return None

            ts = meta.get('system:time_start')
            return {
                'S1_VV': float(s1_vals['VV']),
                'S1_VH': float(s1_vals.get('VH', -18.0)),
                'S1_RVI': float(s1_vals.get('S1_RVI', 0.4)),
                'acquisition_date': datetime.fromtimestamp(ts / 1000.0) if ts else end_dt,
            }
        except Exception as e:
            logger.warning(f"Sentinel-1 fetch skipped/failed: {e}")
            return None

    def _get_time_series(self, col, ee_geom, limit=12):
        """Extract up to `limit` historical Sentinel-2 dates in a single server-side batch call."""
        try:
            recent = col.sort('system:time_start', False).limit(limit)

            def _per_image(img):
                masked = self.calculate_indices(self.mask_clouds(img)).select(OPTICAL_BANDS)
                vals = masked.reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=ee_geom,
                    scale=20,
                    maxPixels=1e8,
                    bestEffort=True,
                )
                return ee.Feature(None, vals).set({
                    'time_start': img.get('system:time_start'),
                    'cloud_cover': img.get('CLOUDY_PIXEL_PERCENTAGE'),
                })

            fc = recent.map(_per_image).getInfo()
            series = []
            for feat in fc.get('features', []):
                props = feat.get('properties', {})
                if props.get('NDVI') is None or props.get('time_start') is None:
                    continue
                dt = datetime.fromtimestamp(props['time_start'] / 1000.0)
                series.append({
                    'acquisition_date': dt,
                    'cloud_cover': float(props.get('cloud_cover') or 0.0),
                    'NDVI': float(props['NDVI']),
                    'EVI': float(props.get('EVI') if props.get('EVI') is not None else props['NDVI']),
                    'SAVI': float(props.get('SAVI') if props.get('SAVI') is not None else props['NDVI']),
                    'GNDVI': float(props.get('GNDVI') if props.get('GNDVI') is not None else props['NDVI']),
                    'NDMI': float(props.get('NDMI') if props.get('NDMI') is not None else 0.0),
                    'NDRE': float(props.get('NDRE') if props.get('NDRE') is not None else 0.0),
                })
            series.sort(key=lambda x: x['acquisition_date'])
            return series
        except Exception as e:
            logger.warning(f"Time series extraction error: {e}")
            return []

    def analyze_field(self, boundary_geojson, start_date, end_date, cloud_max=20, zone_geoms=None):
        """Full pipeline: Sentinel-2 optical + 6-month phenology series + Sentinel-1 SAR radar."""
        import geojson
        geom = geojson.loads(boundary_geojson)
        ee_geom = ee.Geometry(geom)

        s1_stats = self._get_sentinel1_stats(ee_geom, end_date)
        col = self.get_sentinel2_collection(ee_geom, start_date, end_date, cloud_max)
        raw_image = col.sort('system:time_start', False).first()

        meta = None
        if raw_image is not None:
            try:
                meta = raw_image.toDictionary(['system:time_start', 'CLOUDY_PIXEL_PERCENTAGE']).getInfo()
            except Exception:
                meta = None

        if not meta:
            if not s1_stats:
                return None
            return {
                'optical_available': False,
                'radar_available': True,
                's1_stats': s1_stats,
                'ndvi_stats': {'NDVI_mean': 0.0, 'NDVI_min': 0.0, 'NDVI_max': 0.0, 'NDVI_stdDev': 0.0},
                'evi_stats': {'EVI_mean': 0.0, 'EVI_min': 0.0, 'EVI_max': 0.0, 'EVI_stdDev': 0.0},
                'savi_stats': {'SAVI_mean': 0.0, 'SAVI_min': 0.0, 'SAVI_max': 0.0, 'SAVI_stdDev': 0.0},
                'gndvi_stats': {'GNDVI_mean': 0.0, 'GNDVI_min': 0.0, 'GNDVI_max': 0.0, 'GNDVI_stdDev': 0.0},
                'ndmi_stats': {'NDMI_mean': 0.0, 'NDMI_min': 0.0, 'NDMI_max': 0.0, 'NDMI_stdDev': 0.0},
                'ndre_stats': {'NDRE_mean': 0.0, 'NDRE_min': 0.0, 'NDRE_max': 0.0, 'NDRE_stdDev': 0.0},
                'zone_stats': {},
                'time_series': [],
                'is_demo': False,
                'cloud_cover': 100.0,
                'acquisition_date': s1_stats['acquisition_date'],
            }

        time_start = meta.get('system:time_start')
        cloud_pct = meta.get('CLOUDY_PIXEL_PERCENTAGE')

        image = self.calculate_indices(self.mask_clouds(raw_image)).select(OPTICAL_BANDS)
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
            image = self.calculate_indices(composite).select(OPTICAL_BANDS)
            stats = image.reduceRegion(
                reducer=reducer,
                geometry=ee_geom,
                scale=20,
                maxPixels=1e9,
                bestEffort=True,
            ).getInfo()

        if not stats or stats.get('NDVI_mean') is None:
            if not s1_stats:
                return None

        # Per-zone statistics in one batch reduceRegions call
        zone_stats = {}
        if zone_geoms and stats and stats.get('NDVI_mean') is not None:
            features = [
                ee.Feature(ee.Geometry(z_geo), {'cell_idx': idx})
                for idx, z_geo in enumerate(zone_geoms)
            ]
            rr = image.reduceRegions(
                collection=ee.FeatureCollection(features),
                reducer=ee.Reducer.mean(),
                scale=10,
            ).getInfo()

            for feat in rr.get('features', []):
                props = feat.get('properties', {})
                c_idx = props.get('cell_idx')
                if c_idx is not None and props.get('NDVI') is not None:
                    zone_stats[int(c_idx)] = {
                        'NDVI': float(props['NDVI']),
                        'NDMI': float(props.get('NDMI') if props.get('NDMI') is not None else stats.get('NDMI_mean', 0.0)),
                        'NDRE': float(props.get('NDRE') if props.get('NDRE') is not None else stats.get('NDRE_mean', 0.0)),
                    }

            if len(zone_stats) < len(zone_geoms):
                missing = [
                    ee.Feature(ee.Geometry(zone_geoms[idx]), {'cell_idx': idx})
                    for idx in range(len(zone_geoms))
                    if idx not in zone_stats
                ]
                if missing:
                    comp_img = self.calculate_indices(col.map(self.mask_clouds).median()).select(OPTICAL_BANDS)
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
                                'NDVI': float(props['NDVI']),
                                'NDMI': float(props.get('NDMI') if props.get('NDMI') is not None else stats.get('NDMI_mean', 0.0)),
                                'NDRE': float(props.get('NDRE') if props.get('NDRE') is not None else stats.get('NDRE_mean', 0.0)),
                            }

        time_series = self._get_time_series(col, ee_geom, limit=12)

        def _pack(name):
            return {
                f'{name}_mean': float(stats.get(f'{name}_mean') or 0.0),
                f'{name}_min': float(stats.get(f'{name}_min') or 0.0),
                f'{name}_max': float(stats.get(f'{name}_max') or 0.0),
                f'{name}_stdDev': float(stats.get(f'{name}_stdDev') or 0.0),
            }

        return {
            'optical_available': True,
            'radar_available': s1_stats is not None,
            's1_stats': s1_stats,
            'ndvi_stats': _pack('NDVI'),
            'evi_stats': _pack('EVI'),
            'savi_stats': _pack('SAVI'),
            'gndvi_stats': _pack('GNDVI'),
            'ndmi_stats': _pack('NDMI'),
            'ndre_stats': _pack('NDRE'),
            'zone_stats': zone_stats,
            'time_series': time_series,
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
        """Simulate [DEMO] Sentinel-2 + Sentinel-1 + 6-month phenology series."""
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

        now = datetime.utcnow()
        curve = [0.22, 0.31, 0.44, 0.58, 0.72, 0.76, 0.69, ndvi_mean]
        time_series = []
        for i, val in enumerate(curve):
            dt = now - timedelta(days=(len(curve) - 1 - i) * 18)
            time_series.append({
                'acquisition_date': dt,
                'cloud_cover': round(random.uniform(1, 12), 1),
                'NDVI': round(val, 4),
                'EVI': round(val * 0.88, 4),
                'SAVI': round(val * 0.82, 4),
                'GNDVI': round(val * 0.92, 4),
                'NDMI': round(val - 0.14, 4),
                'NDRE': round(val - 0.18, 4),
            })

        return {
            'optical_available': True,
            'radar_available': True,
            's1_stats': {
                'S1_VV': round(random.uniform(-12.5, -8.5), 2),
                'S1_VH': round(random.uniform(-19.0, -14.5), 2),
                'S1_RVI': round(random.uniform(0.45, 0.72), 3),
                'acquisition_date': now - timedelta(days=2),
            },
            'ndvi_stats': {'NDVI_mean': ndvi_mean, 'NDVI_min': ndvi_mean - 0.2, 'NDVI_max': ndvi_mean + 0.1, 'NDVI_stdDev': 0.05},
            'evi_stats': {'EVI_mean': evi_mean, 'EVI_min': evi_mean - 0.18, 'EVI_max': evi_mean + 0.08, 'EVI_stdDev': 0.04},
            'savi_stats': {'SAVI_mean': savi_mean, 'SAVI_min': savi_mean - 0.16, 'SAVI_max': savi_mean + 0.08, 'SAVI_stdDev': 0.04},
            'gndvi_stats': {'GNDVI_mean': gndvi_mean, 'GNDVI_min': gndvi_mean - 0.15, 'GNDVI_max': gndvi_mean + 0.07, 'GNDVI_stdDev': 0.04},
            'ndmi_stats': {'NDMI_mean': ndmi_mean, 'NDMI_min': ndmi_mean - 0.2, 'NDMI_max': ndmi_mean + 0.2, 'NDMI_stdDev': 0.04},
            'ndre_stats': {'NDRE_mean': ndre_mean, 'NDRE_min': ndre_mean - 0.2, 'NDRE_max': ndre_mean + 0.2, 'NDRE_stdDev': 0.06},
            'zone_stats': zone_stats,
            'time_series': time_series,
            'is_demo': True,
            'cloud_cover': random.uniform(0, 10),
            'acquisition_date': now - timedelta(days=2),
            'demo_warning': "[DEMO] Simulated data — not from actual satellite imagery",
        }

    def get_tile_url(self, image, vis_params):
        return "https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}"


def get_gee_service():
    if settings.DEMO_MODE:
        return DemoGEEService()
    return GEEService()
