from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class FieldBase(BaseModel):
    name: str
    boundary_geojson: str
    crop_type: Optional[str] = None
    growth_stage: Optional[str] = None
    area_ha: Optional[float] = None

class FieldCreate(FieldBase):
    farm_id: int

class FieldUpdate(BaseModel):
    name: Optional[str] = None
    boundary_geojson: Optional[str] = None
    crop_type: Optional[str] = None
    growth_stage: Optional[str] = None
    area_ha: Optional[float] = None

class FieldResponse(FieldBase):
    id: int
    farm_id: int
    created_at: datetime
    class Config:
        from_attributes = True
