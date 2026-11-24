from __future__ import annotations

import os
import json
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.field import Field
from backend.models.recommendation import Recommendation
from backend.models.report import Report
from backend.models.satellite import SatelliteObservation
from backend.schemas.report import ReportResponse
from backend.services.report_service import ReportService

router = APIRouter()
REPORTS_DIR = os.path.join(os.getcwd(), "generated_reports")


class ReportGenerateInput(BaseModel):
    title: Optional[str] = None
    report_type: str = "field_summary"


def _build_pdf(field: Field, db: Session, file_path: str) -> str:
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    observations = (
        db.query(SatelliteObservation)
        .filter(SatelliteObservation.field_id == field.id)
        .order_by(SatelliteObservation.acquisition_date.desc())
        .all()
    )
    recommendations = (
        db.query(Recommendation)
        .filter(Recommendation.field_id == field.id)
        .order_by(Recommendation.created_at.desc())
        .all()
    )
    ReportService().generate_pdf_report(field, observations, recommendations, file_path)
    return file_path


@router.get("/fields/{field_id}/reports", response_model=list[ReportResponse])
def list_field_reports(field_id: int, db: Session = Depends(get_db)):
    return (
        db.query(Report)
        .filter(Report.field_id == field_id)
        .order_by(Report.created_at.desc())
        .all()
    )


@router.post("/fields/{field_id}/reports", response_model=ReportResponse)
def generate_field_report(field_id: int, payload: Optional[ReportGenerateInput] = None, db: Session = Depends(get_db)):
    field = db.query(Field).filter(Field.id == field_id).first()
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")

    os.makedirs(REPORTS_DIR, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join(REPORTS_DIR, f"field_{field_id}_{stamp}.pdf")
    _build_pdf(field, db, file_path)

    obs_ids = [o.id for o in db.query(SatelliteObservation).filter(SatelliteObservation.field_id == field_id).all()]
    title = (payload.title if payload and payload.title else f"{field.name} Scouting Report ({datetime.utcnow().strftime('%Y-%m-%d')})")
    report_type = payload.report_type if payload else "field_summary"

    db_report = Report(
        field_id=field_id,
        title=title,
        report_type=report_type,
        file_path=file_path,
        included_observations=json.dumps(obs_ids),
    )
    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    return db_report


@router.get("/reports/{report_id}", response_model=ReportResponse)
def get_report(report_id: int, db: Session = Depends(get_db)):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@router.get("/reports/{report_id}/download")
def download_report(report_id: int, db: Session = Depends(get_db)):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    if not os.path.exists(report.file_path):
        field = db.query(Field).filter(Field.id == report.field_id).first()
        if not field:
            raise HTTPException(status_code=404, detail="Field not found")
        _build_pdf(field, db, report.file_path)

    return FileResponse(
        path=report.file_path,
        media_type="application/pdf",
        filename=f"farm_scouting_report_{report.id}.pdf",
    )
