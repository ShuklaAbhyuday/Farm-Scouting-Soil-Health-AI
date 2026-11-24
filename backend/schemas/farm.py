from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class FarmBase(BaseModel):
    name: str
    location_description: Optional[str] = None
    center_lat: float
    center_lng: float
    total_area_ha: Optional[float] = None

class FarmCreate(FarmBase):
    user_id: int

class FarmUpdate(BaseModel):
    name: Optional[str] = None
    location_description: Optional[str] = None
    center_lat: Optional[float] = None
    center_lng: Optional[float] = None
    total_area_ha: Optional[float] = None

class FarmResponse(FarmBase):
    id: int
    user_id: int
    created_at: datetime
    class Config:
        from_attributes = True
