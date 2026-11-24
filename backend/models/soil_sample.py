from __future__ import annotations
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from backend.database import Base

class SoilSample(Base):
    __tablename__ = "soil_samples"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    field_id = Column(Integer, ForeignKey("fields.id"))
    hotspot_id = Column(Integer, ForeignKey("hotspots.id"), nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    nitrogen_level = Column(String, nullable=True) # "low", "medium", "high"
    nitrogen_value = Column(Float, nullable=True)
    phosphorus_level = Column(String, nullable=True)
    phosphorus_value = Column(Float, nullable=True)
    potassium_level = Column(String, nullable=True)
    potassium_value = Column(Float, nullable=True)
    ph_value = Column(Float, nullable=True)
    moisture_level = Column(String, nullable=True)
    moisture_value = Column(Float, nullable=True)
    soil_texture = Column(String, nullable=True)
    sample_date = Column(DateTime, nullable=False)
    source = Column(String, nullable=False) # "manual", "lab", "sensor"
    is_validated = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    field = relationship("Field", back_populates="soil_samples")
    hotspot = relationship("Hotspot", back_populates="soil_samples")
