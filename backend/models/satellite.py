from __future__ import annotations
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from backend.database import Base

class SatelliteObservation(Base):
    __tablename__ = "satellite_observations"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    field_id = Column(Integer, ForeignKey("fields.id"))
    source = Column(String, default="sentinel-2")
    collection_id = Column(String, nullable=True)
    image_id = Column(String, nullable=True)
    acquisition_date = Column(DateTime, nullable=False)
    cloud_cover_pct = Column(Float, nullable=False)
    bands_metadata = Column(Text, nullable=True)
    status = Column(String, default="pending")
    processed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    field = relationship("Field", back_populates="observations")
    index_results = relationship("IndexResult", back_populates="observation")
    hotspots = relationship("Hotspot", back_populates="observation")

class IndexResult(Base):
    __tablename__ = "index_results"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    observation_id = Column(Integer, ForeignKey("satellite_observations.id"))
    index_type = Column(String, nullable=False) # ndvi, ndmi, ndre
    mean_value = Column(Float, nullable=False)
    min_value = Column(Float, nullable=False)
    max_value = Column(Float, nullable=False)
    std_value = Column(Float, nullable=False)
    raster_data = Column(Text, nullable=True) # base64 or path
    statistics = Column(Text, nullable=True) # JSON
    created_at = Column(DateTime, default=datetime.utcnow)
    
    observation = relationship("SatelliteObservation", back_populates="index_results")
