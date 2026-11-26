import io
import json
import os
import tempfile
import unittest
from datetime import datetime

from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base, get_db
from backend.main import app
from backend.models.farm import Farm
from backend.models.field import Field
from backend.models.soil_sample import SoilSample

SAMPLE_POLYGON = json.dumps({
    "type": "Polygon",
    "coordinates": [[
        [77.5900, 13.0800],
        [77.5920, 13.0800],
        [77.5920, 13.0820],
        [77.5900, 13.0820],
        [77.5900, 13.0800],
    ]],
})


def _make_pdf_bytes(lines: list[str]) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    y = 780
    for line in lines:
        c.drawString(60, y, line)
        y -= 20
    c.save()
    buf.seek(0)
    return buf.read()


class TestSoilPdfAndFertilizerRecommendation(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.tmpdir.name, "test_fert_pdf.db")
        self.engine = create_engine(
            f"sqlite:///{self.db_path}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

        def override_get_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

        db = self.SessionLocal()
        try:
            farm = Farm(name="Test Farm", center_lat=13.081, center_lng=77.591, total_area_ha=5.0)
            db.add(farm)
            db.commit()
            db.refresh(farm)
            field = Field(
                farm_id=farm.id,
                name="Plot Alpha",
                crop_type="Wheat",
                boundary_geojson=SAMPLE_POLYGON,
                area_ha=4.0,
            )
            db.add(field)
            db.commit()
            db.refresh(field)
            self.field_id = field.id
        finally:
            db.close()

    def tearDown(self):
        app.dependency_overrides.clear()
        self.engine.dispose()
        self.tmpdir.cleanup()

    def test_parse_soil_report_pdf_extracts_metrics_and_conversions(self):
        pdf_bytes = _make_pdf_bytes([
            "GREEN VALLEY SOIL TESTING LABORATORY",
            "Sample ID: GV-2026-014",
            "Available Nitrogen (N): 33.6 kg/ha",
            "Available Phosphorus (P): 12.0 mg/kg",
            "Available Potassium (K): 145 ppm",
            "Soil pH (1:2.5): 5.5",
            "Soil Moisture: 22%",
            "Soil Texture: Clay Loam",
        ])

        resp = self.client.post(
            "/api/soil-samples/parse-pdf",
            files={"file": ("lab_report.pdf", pdf_bytes, "application/pdf")},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["extraction_success"])
        self.assertEqual(data["missing_keys"], [])
        self.assertEqual(data["parsed_fields"]["nitrogen_value"], 15.0)  # 33.6 / 2.24
        self.assertEqual(data["parsed_fields"]["nitrogen_level"], "low")
        self.assertEqual(data["parsed_fields"]["phosphorus_value"], 12.0)
        self.assertEqual(data["parsed_fields"]["phosphorus_level"], "low")
        self.assertEqual(data["parsed_fields"]["potassium_value"], 145.0)
        self.assertEqual(data["parsed_fields"]["potassium_level"], "medium")
        self.assertEqual(data["parsed_fields"]["ph_value"], 5.5)
        self.assertEqual(data["parsed_fields"]["moisture_level"], "medium")
        self.assertEqual(data["parsed_fields"]["soil_texture"], "Clay Loam")
        self.assertEqual(len(data["unit_conversions"]), 1)

    def test_parse_soil_report_pdf_rejects_non_pdf_and_preserves_missing_as_null(self):
        bad = self.client.post(
            "/api/soil-samples/parse-pdf",
            files={"file": ("notes.txt", b"N: 15", "text/plain")},
        )
        self.assertEqual(bad.status_code, 400)

        partial_pdf = _make_pdf_bytes(["Soil pH: 6.7", "Texture: Sandy Loam"])
        res = self.client.post(
            "/api/soil-samples/parse-pdf",
            files={"file": ("partial.pdf", partial_pdf, "application/pdf")},
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["extraction_success"])
        self.assertIsNone(body["parsed_fields"]["nitrogen_value"])
        self.assertIn("nitrogen", body["missing_keys"])
        self.assertEqual(body["parsed_fields"]["ph_value"], 6.7)
        self.assertEqual(body["parsed_fields"]["soil_texture"], "Sandy Loam")

    def test_parse_tabular_and_oxide_soil_report_without_false_positive_sample_numbers(self):
        tabular_pdf = _make_pdf_bytes([
            "S. N. : 1  Report No: 999",
            "Available Nitrogen   Low   kg/ha   44.8",
            "Available P2O5       kg/ha   22.4",
            "Available K2O        ppm     180",
            "pH Value             6.3",
        ])
        res = self.client.post(
            "/api/soil-samples/parse-pdf",
            files={"file": ("shc_table.pdf", tabular_pdf, "application/pdf")},
        )
        self.assertEqual(res.status_code, 200)
        d = res.json()
        self.assertTrue(d["extraction_success"])
        self.assertEqual(d["parsed_fields"]["nitrogen_value"], 20.0)  # 44.8 / 2.24, NOT S. N. : 1
        self.assertEqual(d["parsed_fields"]["phosphorus_value"], 10.0)  # 22.4 / 2.24
        self.assertEqual(d["parsed_fields"]["potassium_value"], 180.0)
        self.assertEqual(d["parsed_fields"]["ph_value"], 6.3)

    def test_fertilizer_recommendation_system_gating_and_verified_scaling(self):
        # 1. No soil sample -> withholds dosages
        empty = self.client.get(f"/api/fields/{self.field_id}/fertilizer-recommendation").json()
        self.assertEqual(empty["status"], "soil_sample_required")
        self.assertFalse(empty["can_prescribe_dosage"])
        self.assertEqual(empty["recommendations"], [])

        # 2. Unvalidated sample -> locks exact kg/ha rates
        db = self.SessionLocal()
        unval = SoilSample(
            field_id=self.field_id,
            latitude=13.081,
            longitude=77.591,
            nitrogen_level="low",
            nitrogen_value=14.0,
            phosphorus_level="low",
            phosphorus_value=10.0,
            potassium_level="medium",
            potassium_value=140.0,
            ph_value=5.5,
            soil_texture="Clay Loam",
            sample_date=datetime.utcnow(),
            source="manual",
            is_validated=False,
        )
        db.add(unval)
        db.commit()
        db.refresh(unval)
        unval_id = unval.id
        db.close()

        est = self.client.get(f"/api/fields/{self.field_id}/fertilizer-recommendation?sample_id={unval_id}").json()
        self.assertEqual(est["status"], "unvalidated_estimate")
        self.assertFalse(est["can_prescribe_dosage"])
        self.assertTrue(all(r["rate_kg_ha"] is None for r in est["recommendations"]))

        # 3. Validated sample -> unlocks exact kg/ha, 4.0 ha field scaling, and pH Lime amendment
        db = self.SessionLocal()
        val = SoilSample(
            field_id=self.field_id,
            latitude=13.081,
            longitude=77.591,
            nitrogen_level="low",
            nitrogen_value=14.0,
            phosphorus_level="low",
            phosphorus_value=10.0,
            potassium_level="medium",
            potassium_value=140.0,
            ph_value=5.5,
            soil_texture="Clay Loam",
            sample_date=datetime.utcnow(),
            source="lab",
            is_validated=True,
        )
        db.add(val)
        db.commit()
        db.refresh(val)
        val_id = val.id
        db.close()

        plan = self.client.get(f"/api/fields/{self.field_id}/fertilizer-recommendation?sample_id={val_id}").json()
        self.assertEqual(plan["status"], "lab_verified_plan")
        self.assertTrue(plan["can_prescribe_dosage"])
        self.assertEqual(plan["area_ha"], 4.0)
        self.assertIsNotNone(plan["ph_amendment"])
        self.assertEqual(plan["ph_amendment"]["rate_kg_ha"], 300.0)
        self.assertEqual(plan["ph_amendment"]["total_field_kg"], 1200.0)
        for r in plan["recommendations"]:
            self.assertIsNotNone(r["rate_kg_ha"])
            if r["rate_kg_ha"] > 0:
                self.assertAlmostEqual(r["total_field_kg"], round(r["rate_kg_ha"] * 4.0, 1), places=1)


if __name__ == "__main__":
    unittest.main()
