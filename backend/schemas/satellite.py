from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class IndexResultBase(BaseModel):
    """
    Formulas:
    - NDVI = (NIR_B8 - Red_B4) / (NIR_B8 + Red_B4)
    - NDMI = (NIR_B8 - SWIR_B11) / (NIR_B8 + SWIR_B11)
    - NDRE = (NIR_B8 - RedEdge_B5) / (NIR_B8 + RedEdge_B5)
    """
    index_type: str
    mean_value: float
    min_value: float
    max_value: float
    std_value: float
    raster_data: Optional[str] = None
    statistics: Optional[str] = None

class IndexResultCreate(IndexResultBase):
    observation_id: int

class IndexResultResponse(IndexResultBase):
    id: int
    observation_id: int
    created_at: datetime
    class Config:
        from_attributes = True

class SatelliteObservationBase(BaseModel):
    source: str = "sentinel-2"
    collection_id: Optional[str] = None
    image_id: Optional[str] = None
    acquisition_date: datetime
    cloud_cover_pct: float
    bands_metadata: Optional[str] = None
    status: str = "pending"
    processed_at: Optional[datetime] = None

class SatelliteObservationCreate(SatelliteObservationBase):
    field_id: int

class SatelliteObservationUpdate(BaseModel):
    status: Optional[str] = None
    processed_at: Optional[datetime] = None

class SatelliteObservationResponse(SatelliteObservationBase):
    id: int
    field_id: int
    created_at: datetime
    class Config:
        from_attributes = True
