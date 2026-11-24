from __future__ import annotations
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from backend.database import Base

class Recommendation(Base):
    __tablename__ = "recommendations"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    field_id = Column(Integer, ForeignKey("fields.id"))
    hotspot_id = Column(Integer, ForeignKey("hotspots.id"), nullable=True)
    category = Column(String, nullable=False) # "fertilizer", "irrigation", "crop", "soil"
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    reasoning = Column(Text, nullable=False)
    satellite_evidence = Column(Text, nullable=True) # JSON
    ground_truth_evidence = Column(Text, nullable=True) # JSON
    confidence = Column(String, nullable=False) # "low", "medium", "high"
    priority = Column(String, nullable=False) # "low", "medium", "high", "critical"
    requires_ground_truth = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    field = relationship("Field", back_populates="recommendations")
    hotspot = relationship("Hotspot", back_populates="recommendations")
