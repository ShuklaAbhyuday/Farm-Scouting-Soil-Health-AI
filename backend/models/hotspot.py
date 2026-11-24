from __future__ import annotations
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from backend.database import Base

class Hotspot(Base):
    __tablename__ = "hotspots"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    field_id = Column(Integer, ForeignKey("fields.id"))
    observation_id = Column(Integer, ForeignKey("satellite_observations.id"))
    geometry_geojson = Column(Text, nullable=False)
    center_lat = Column(Float, nullable=False)
    center_lng = Column(Float, nullable=False)
    area_ha = Column(Float, nullable=False)
    severity = Column(String, nullable=False)
    health_score = Column(Float, nullable=False)
    ndvi_value = Column(Float, nullable=True)
    ndmi_value = Column(Float, nullable=True)
    ndre_value = Column(Float, nullable=True)
    ndvi_deviation = Column(Float, nullable=True)
    ndmi_deviation = Column(Float, nullable=True)
    ndre_deviation = Column(Float, nullable=True)
    likely_issue = Column(String, nullable=True)
    explanation = Column(Text, nullable=True)
    detection_method = Column(String, nullable=False) # "baseline_heuristic" or "isolation_forest"
    persistence_count = Column(Integer, default=1)
    first_detected = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    field = relationship("Field", back_populates="hotspots")
    observation = relationship("SatelliteObservation", back_populates="hotspots")
    soil_samples = relationship("SoilSample", back_populates="hotspot")
    recommendations = relationship("Recommendation", back_populates="hotspot")
