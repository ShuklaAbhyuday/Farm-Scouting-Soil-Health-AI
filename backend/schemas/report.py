from pydantic import BaseModel
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
