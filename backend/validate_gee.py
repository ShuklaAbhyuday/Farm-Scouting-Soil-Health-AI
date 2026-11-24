"""
GEE → Sentinel-2 → NDVI Pipeline Validation Script

Run this BEFORE building the rest of the application to verify
that the GEE integration works correctly.

Usage:
  python validate_gee.py --project YOUR_GEE_PROJECT_ID
  python validate_gee.py --demo  (uses demo data)
"""
import argparse
import sys
from backend.config import settings

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', type=str, help='GEE Project ID')
    parser.add_argument('--demo', action='store_true', help='Use demo mode')
    args = parser.parse_args()
    
    if args.demo:
        settings.DEMO_MODE = True
        print("Using Demo mode...")
    else:
        settings.DEMO_MODE = False
        if args.project:
            settings.GEE_PROJECT_ID = args.project
            
    from backend.services.gee_service import get_gee_service
    gee = get_gee_service()
    
    print("1. Initializing GEE...")
    if not gee.initialize():
        print("Failed to initialize GEE!")
        sys.exit(1)
        
    print("2. Defined test polygon")
    test_geojson = '{"type": "Polygon", "coordinates": [[[-121.8, 37.9], [-121.8, 37.8], [-121.7, 37.8], [-121.7, 37.9], [-121.8, 37.9]]]}'
    
    print("3. Querying Sentinel-2 & 4. Cloud masking & 5. Calculating Indices & 6. Printing statistics...")
    try:
        res = gee.analyze_field(test_geojson, "2023-01-01", "2023-02-01", 20)
        if res:
            print(f"Success! Stats: {res}")
            print("7. Test NDVI stats extracted.")
        else:
            print("No images found in date range.")
    except Exception as e:
        print(f"Error analyzing field: {e}")
        
    print("8. Validation script finished.")

if __name__ == "__main__":
    main()
