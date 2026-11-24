from pydantic import BaseModel
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
