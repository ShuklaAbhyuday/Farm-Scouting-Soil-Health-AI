from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from backend.database import get_db
from backend.models.field import Field
from backend.models.satellite import SatelliteObservation, IndexResult
from backend.services.gee_service import get_gee_service

router = APIRouter()

@router.post("/fields/{field_id}/analyze")
def analyze_field(field_id: int, start_date: str, end_date: str, cloud_max: int = 20, db: Session = Depends(get_db)):
    field = db.query(Field).filter(Field.id == field_id).first()
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")
        
    gee = get_gee_service()
    if not gee.initialize():
        raise HTTPException(status_code=500, detail="GEE Initialization failed")
        
    results = gee.analyze_field(field.boundary_geojson, start_date, end_date, cloud_max)
    if not results:
        raise HTTPException(status_code=404, detail="No valid satellite data found in date range")
        
    obs = SatelliteObservation(
        field_id=field_id,
        acquisition_date=results['acquisition_date'],
        cloud_cover_pct=results['cloud_cover'],
        status='processed',
        processed_at=datetime.utcnow()
    )
    db.add(obs)
    db.commit()
    db.refresh(obs)
    
    # Add index results...
    for idx_name, stats in zip(['NDVI', 'NDMI', 'NDRE'], [results['ndvi_stats'], results['ndmi_stats'], results['ndre_stats']]):
        idx_res = IndexResult(
            observation_id=obs.id,
            index_type=idx_name,
            mean_value=stats[f'{idx_name}_mean'],
            min_value=stats[f'{idx_name}_min'],
            max_value=stats[f'{idx_name}_max'],
            std_value=stats[f'{idx_name}_stdDev']
        )
        db.add(idx_res)
    db.commit()
    
    return {"message": "Analysis complete", "observation_id": obs.id}

@router.get("/observations/{id}/tiles/{index_type}/{z}/{x}/{y}.png")
def get_tile(id: int, index_type: str, z: int, x: int, y: int):
    # This would normally proxy to GEE getTileUrl, returning a static image for demo
    from fastapi.responses import FileResponse
    # Returning a 404 since we don't have an actual tile server implementation here
    raise HTTPException(status_code=404, detail="Tile proxy not fully implemented")
