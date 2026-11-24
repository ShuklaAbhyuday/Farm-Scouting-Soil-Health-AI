from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models.hotspot import Hotspot
from backend.schemas.hotspot import HotspotCreate, HotspotResponse

router = APIRouter()

@router.post("/", response_model=HotspotResponse)
def create_hotspot(hotspot: HotspotCreate, db: Session = Depends(get_db)):
    db_hotspot = Hotspot(**hotspot.dict())
    db.add(db_hotspot)
    db.commit()
    db.refresh(db_hotspot)
    return db_hotspot

@router.get("/{hotspot_id}", response_model=HotspotResponse)
def get_hotspot(hotspot_id: int, db: Session = Depends(get_db)):
    hotspot = db.query(Hotspot).filter(Hotspot.id == hotspot_id).first()
    if not hotspot:
        raise HTTPException(status_code=404, detail="Hotspot not found")
    return hotspot
