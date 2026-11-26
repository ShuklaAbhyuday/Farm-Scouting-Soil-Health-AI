from __future__ import annotations

from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import relationship
from backend.database import Base


class SatelliteObservation(Base):
    __tablename__ = "satellite_observations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    field_id = Column(Integer, ForeignKey("fields.id"))
    # Strict sensor/provenance values: "sentinel-2", "sentinel-1", "demo-simulation"
    source = Column(String, nullable=False, default="sentinel-2")
    collection_id = Column(String, nullable=True)
    image_id = Column(String, nullable=True)
    acquisition_date = Column(DateTime, nullable=False)
    # Canonical YYYY-MM-DD UTC date used with partial unique index for idempotent per-sensor upserts
    acquisition_day = Column(String, nullable=False)
    # NULL for Sentinel-1 SAR (cloud-independent); float percentage for optical Sentinel-2
    cloud_cover_pct = Column(Float, nullable=True)
    # Field-level fraction of unmasked valid pixels [0..100] and composite provenance
    valid_pixel_pct = Column(Float, nullable=True)
    observation_count = Column(Integer, nullable=True)
    composite_method = Column(String, nullable=True)
    bands_metadata = Column(Text, nullable=True)
    status = Column(String, default="pending")
    is_demo = Column(Boolean, default=False, nullable=False)
    is_superseded = Column(Boolean, default=False, nullable=False)
    processed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    field = relationship("Field", back_populates="observations")
    index_results = relationship("IndexResult", back_populates="observation")
    hotspots = relationship("Hotspot", back_populates="observation")

    __table_args__ = (
        Index(
            "uq_active_obs_per_day",
            "field_id",
            "source",
            "acquisition_day",
            unique=True,
            sqlite_where=text("is_superseded = 0"),
        ),
    )


class IndexResult(Base):
    __tablename__ = "index_results"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    observation_id = Column(Integer, ForeignKey("satellite_observations.id"))
    index_type = Column(String, nullable=False)
    # Nullable so unmeasured / cloud-masked indices are stored as NULL rather than fabricated 0.0
    mean_value = Column(Float, nullable=True)
    min_value = Column(Float, nullable=True)
    max_value = Column(Float, nullable=True)
    std_value = Column(Float, nullable=True)
    raster_data = Column(Text, nullable=True)
    statistics = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    observation = relationship("SatelliteObservation", back_populates="index_results")
