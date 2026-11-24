from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class HotspotBase(BaseModel):
    geometry_geojson: str
    center_lat: float
    center_lng: float
    area_ha: float
    severity: str
    health_score: float
    ndvi_value: Optional[float] = None
    ndmi_value: Optional[float] = None
    ndre_value: Optional[float] = None
    ndvi_deviation: Optional[float] = None
    ndmi_deviation: Optional[float] = None
    ndre_deviation: Optional[float] = None
    likely_issue: Optional[str] = None
    explanation: Optional[str] = None
    detection_method: str
    persistence_count: int = 1
    first_detected: datetime

class HotspotCreate(HotspotBase):
    field_id: int
    observation_id: int

class HotspotUpdate(BaseModel):
    severity: Optional[str] = None
    health_score: Optional[float] = None
    likely_issue: Optional[str] = None
    explanation: Optional[str] = None
    persistence_count: Optional[int] = None

class HotspotResponse(HotspotBase):
    id: int
    field_id: int
    observation_id: int
    created_at: datetime
    class Config:
        from_attributes = True
