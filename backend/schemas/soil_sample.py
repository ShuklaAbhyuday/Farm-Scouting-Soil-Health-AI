from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class SoilSampleBase(BaseModel):
    latitude: float
    longitude: float
    nitrogen_level: Optional[str] = None
    nitrogen_value: Optional[float] = None
    phosphorus_level: Optional[str] = None
    phosphorus_value: Optional[float] = None
    potassium_level: Optional[str] = None
    potassium_value: Optional[float] = None
    ph_value: Optional[float] = None
    moisture_level: Optional[str] = None
    moisture_value: Optional[float] = None
    soil_texture: Optional[str] = None
    sample_date: datetime
    source: str
    is_validated: bool = False
    notes: Optional[str] = None

class SoilSampleCreate(SoilSampleBase):
    field_id: int
    hotspot_id: Optional[int] = None

class SoilSampleUpdate(BaseModel):
    is_validated: Optional[bool] = None
    notes: Optional[str] = None
    nitrogen_level: Optional[str] = None
    nitrogen_value: Optional[float] = None
    phosphorus_level: Optional[str] = None
    phosphorus_value: Optional[float] = None
    potassium_level: Optional[str] = None
    potassium_value: Optional[float] = None
    ph_value: Optional[float] = None
    moisture_level: Optional[str] = None
    moisture_value: Optional[float] = None
    soil_texture: Optional[str] = None

class SoilSampleResponse(SoilSampleBase):
    id: int
    field_id: int
    hotspot_id: Optional[int] = None
    created_at: datetime
    class Config:
        from_attributes = True
