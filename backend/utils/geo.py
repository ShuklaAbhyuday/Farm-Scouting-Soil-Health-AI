import geojson
from shapely.geometry import shape

def geojson_to_ee_geometry(geojson_str):
    import ee
    geom = geojson.loads(geojson_str)
    return ee.Geometry(geom)

def calculate_area_ha(geojson_str):
    """Calculate area in hectares from GeoJSON polygon."""
    geom = geojson.loads(geojson_str)
    s_geom = shape(geom)
    # Simple approx: area in deg^2 * roughly 1e10 sq meters / 10000 = hectares
    # In a real app we'd project to equal area first
    approx_ha = s_geom.area * 1e10 / 10000.0
    return approx_ha

def find_centroid(geojson_str):
    """Find (lat, lng) centroid of GeoJSON polygon."""
    geom = geojson.loads(geojson_str)
    s_geom = shape(geom)
    centroid = s_geom.centroid
    return centroid.y, centroid.x

def check_polygon_valid(geojson_str):
    """Check if GeoJSON is a valid polygon."""
    try:
        geom = geojson.loads(geojson_str)
        s_geom = shape(geom)
        return s_geom.is_valid
    except Exception:
        return False
