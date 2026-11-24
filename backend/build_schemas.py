import os

schemas_dir = r"c:\Users\abhyu\OneDrive\Desktop\EPICS\backend\schemas"
os.makedirs(schemas_dir, exist_ok=True)

files = {
    "__init__.py": "",
    "user.py": """from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional

class UserBase(BaseModel):
    email: EmailStr
    name: str

class UserCreate(UserBase):
    password: Optional[str] = None

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    name: Optional[str] = None
    password: Optional[str] = None

class UserResponse(UserBase):
    id: int
    created_at: datetime
    class Config:
        from_attributes = True
""",
    "farm.py": """from pydantic import BaseModel
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
""",
    "field.py": """from pydantic import BaseModel
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
""",
    "satellite.py": '''from pydantic import BaseModel
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
''',
    "hotspot.py": """from pydantic import BaseModel
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
""",
    "soil_sample.py": """from pydantic import BaseModel
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
""",
    "recommendation.py": """from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class RecommendationBase(BaseModel):
    category: str
    title: str
    description: str
    reasoning: str
    satellite_evidence: Optional[str] = None
    ground_truth_evidence: Optional[str] = None
    confidence: str
    priority: str
    requires_ground_truth: bool = False

class RecommendationCreate(RecommendationBase):
    field_id: int
    hotspot_id: Optional[int] = None

class RecommendationUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    reasoning: Optional[str] = None
    confidence: Optional[str] = None
    priority: Optional[str] = None

class RecommendationResponse(RecommendationBase):
    id: int
    field_id: int
    hotspot_id: Optional[int] = None
    created_at: datetime
    class Config:
        from_attributes = True
""",
    "report.py": """from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class ReportBase(BaseModel):
    title: str
    report_type: str
    file_path: str
    included_observations: Optional[str] = None
    date_range_start: Optional[datetime] = None
    date_range_end: Optional[datetime] = None

class ReportCreate(ReportBase):
    field_id: int

class ReportUpdate(BaseModel):
    title: Optional[str] = None

class ReportResponse(ReportBase):
    id: int
    field_id: int
    created_at: datetime
    class Config:
        from_attributes = True
"""
}

for filename, content in files.items():
    with open(os.path.join(schemas_dir, filename), "w") as f:
        f.write(content)
