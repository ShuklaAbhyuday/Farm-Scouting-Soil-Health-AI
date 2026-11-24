from __future__ import annotations
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from backend.database import Base

class Field(Base):
    __tablename__ = "fields"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    farm_id = Column(Integer, ForeignKey("farms.id"))
    name = Column(String, nullable=False)
    boundary_geojson = Column(Text, nullable=False) # Store as JSON string
    crop_type = Column(String, nullable=True)
    growth_stage = Column(String, nullable=True)
    area_ha = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    farm = relationship("Farm", back_populates="fields")
    observations = relationship("SatelliteObservation", back_populates="field")
    hotspots = relationship("Hotspot", back_populates="field")
    soil_samples = relationship("SoilSample", back_populates="field")
    recommendations = relationship("Recommendation", back_populates="field")
    reports = relationship("Report", back_populates="field")
