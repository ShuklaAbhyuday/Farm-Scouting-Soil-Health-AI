from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models.soil_sample import SoilSample
from backend.schemas.soil_sample import SoilSampleCreate, SoilSampleResponse

router = APIRouter()

@router.post("/", response_model=SoilSampleResponse)
def create_soil_sample(sample: SoilSampleCreate, db: Session = Depends(get_db)):
    db_sample = SoilSample(**sample.dict())
    db.add(db_sample)
    db.commit()
    db.refresh(db_sample)
    return db_sample

@router.get("/{sample_id}", response_model=SoilSampleResponse)
def get_soil_sample(sample_id: int, db: Session = Depends(get_db)):
    sample = db.query(SoilSample).filter(SoilSample.id == sample_id).first()
    if not sample:
        raise HTTPException(status_code=404, detail="SoilSample not found")
    return sample
