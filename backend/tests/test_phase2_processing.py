import json
import math
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

import numpy as np
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base, get_db
from backend.main import app
from backend.migrations.phase2_migration import migrate_phase2_sqlite
from backend.models.farm import Farm
from backend.models.field import Field
from backend.models.satellite import IndexResult, SatelliteObservation
from backend.services.gee_service import (
    S2_MASKED_SCL_CLASSES,
    S2_TILE_CLOUD_PREFILTER_MAX,
    STANDARD_S2_SCALE_M,
    build_10day_composite_bins,
    compute_scl_clear_mask_array,
    group_same_day_scenes,
)
from backend.services.phenology_service import analyze_seasonal_phenology
from backend.services.sar_utils import (
    average_db_via_linear,
    classify_surface_wetness_relative,
    compute_dual_pol_rvi,
    db_to_linear,
    linear_to_db,
    select_consistent_orbit_group,
)

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


class TestPhase2ScientificUnits(unittest.TestCase):
    def test_sentinel2_scl_mask_and_constants(self):
        # Verify invalid (0), defective (1), shadow (3), cloud (8,9,10), snow (11) masked; clear (2,4,5,6,7) kept
        scl = np.array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11])
        clear = compute_scl_clear_mask_array(scl)
        expected = np.array([False, False, True, False, True, True, True, True, False, False, False, False])
        np.testing.assert_array_equal(clear, expected)
        for cls in (0, 1, 3, 8, 9, 10, 11):
            self.assertIn(cls, S2_MASKED_SCL_CLASSES)
        self.assertEqual(STANDARD_S2_SCALE_M, 20)
        self.assertGreaterEqual(S2_TILE_CLOUD_PREFILTER_MAX, 60)

    def test_sentinel2_same_day_grouping_and_180day_10day_bins(self):
        dt_day = datetime(2026, 11, 12, 5, 10, 0)
        scenes = [
            {"acquisition_date": dt_day, "image_id": "T43PGP"},
            {"acquisition_date": dt_day + timedelta(seconds=15), "image_id": "T43PGQ"},
            {"acquisition_date": datetime(2026, 11, 2, 5, 10, 0), "image_id": "T43PGP_PREV"},
        ]
        grouped = group_same_day_scenes(scenes)
        self.assertEqual(len(grouped["2026-11-12"]), 2)
        self.assertEqual(len(grouped["2026-11-02"]), 1)

        end_dt = datetime(2026, 11, 26)
        start_dt = end_dt - timedelta(days=180)
        bins = build_10day_composite_bins(start_dt, end_dt, step_days=10)
        self.assertGreaterEqual(len(bins), 18)
        self.assertEqual(bins[0][0], start_dt)

    def test_sentinel1_linear_power_averaging_and_dual_pol_rvi(self):
        # Naive arithmetic mean of [-14 dB, -6 dB] is -10 dB; linear power mean is higher (~ -8.35 dB)
        avg_db = average_db_via_linear([-14.0, -6.0])
        expected_lin = (10 ** (-1.4) + 10 ** (-0.6)) / 2.0
        self.assertAlmostEqual(avg_db, 10.0 * math.log10(expected_lin), places=6)
        self.assertGreater(avg_db, -10.0)

        vv_lin = db_to_linear(-10.0)  # 0.1
        vh_lin = db_to_linear(-16.0)  # ~0.02511886
        rvi = compute_dual_pol_rvi(vv_lin, vh_lin)
        self.assertAlmostEqual(rvi, 4.0 * vh_lin / (vv_lin + vh_lin), places=6)
        self.assertGreater(rvi, 0.7)
        self.assertLess(rvi, 1.0)
        # Dual-pol RVI > 1.0 when cross-pol approaches co-pol must not be clipped at 1.0
        high_rvi = compute_dual_pol_rvi(0.05, 0.03)
        self.assertGreater(high_rvi, 1.0)
        self.assertAlmostEqual(high_rvi, 1.5, places=6)

        # Round-trip sanity
        self.assertAlmostEqual(linear_to_db(db_to_linear(-11.72)), -11.72, places=6)

    def test_sentinel1_orbit_consistency_and_relative_wetness(self):
        scenes = [
            {"acquisition_date": datetime(2026, 11, 20), "orbit_pass": "DESCENDING", "relative_orbit": 63, "vv_db": -9.0},
            {"acquisition_date": datetime(2026, 11, 14), "orbit_pass": "ASCENDING", "relative_orbit": 114, "vv_db": -14.0},
            {"acquisition_date": datetime(2026, 11, 8), "orbit_pass": "DESCENDING", "relative_orbit": 63, "vv_db": -12.0},
            {"acquisition_date": datetime(2026, 10, 27), "orbit_pass": "DESCENDING", "relative_orbit": 63, "vv_db": -12.2},
        ]
        matched, opass, rorb = select_consistent_orbit_group(scenes)
        self.assertEqual(opass, "DESCENDING")
        self.assertEqual(rorb, 63)
        self.assertEqual(len(matched), 3)
        self.assertTrue(all(s["orbit_pass"] == "DESCENDING" for s in matched))

        # Insufficient baseline refuses fixed dB moisture interpretation
        insuff = classify_surface_wetness_relative(-10.5, delta_vv_db=None, baseline_count=1, orbit_consistent=True)
        self.assertEqual(insuff["method"], "insufficient_same_orbit_baseline")
        self.assertIn("NOT a direct soil moisture", insuff["limitation"])

        # With >=2 same-orbit prior baseline and +2.5 dB rise -> relative wetness proxy
        wet = classify_surface_wetness_relative(-9.5, delta_vv_db=2.5, baseline_count=3, orbit_consistent=True)
        self.assertEqual(wet["method"], "same_orbit_temporal_delta_vv")
        self.assertIn("Elevated Backscatter vs. Orbit Baseline", wet["status"])
        self.assertIn("NOT a direct soil moisture", wet["limitation"])

    def test_phenology_multi_year_separation_gating_rate_and_consecutive_declines(self):
        # Reproduce Field 1 scenario: Dec 2024 (0.2608) + Oct-Nov 2026 (max 0.2208)
        pts = [
            (datetime(2024, 12, 20), 0.2608),
            (datetime(2026, 10, 16), 0.1589),
            (datetime(2026, 10, 31), 0.1267),
            (datetime(2026, 11, 5), 0.2185),
            (datetime(2026, 11, 12), 0.2208),
            (datetime(2026, 11, 15), 0.2015),
        ]
        ph = analyze_seasonal_phenology(pts, crop_type="Wheat")
        self.assertEqual(ph["season_count"], 2)
        self.assertEqual(ph["observation_count"], 5)
        self.assertEqual(ph["peak_ndvi"], 0.2208)
        self.assertEqual(ph["peak_date"], "2026-11-12")
        self.assertEqual(ph["previous_seasons"][0]["peak_date"], "2024-12-20")
        self.assertFalse(ph["crop_calendar_context"]["is_proof_of_stage"])
        # Single dip from 11-12 to 11-15 must NOT trigger senescence/harvest
        self.assertNotIn("Senescence", ph["stage"])
        self.assertNotIn("Harvest", ph["stage"])
        # Elapsed days = 3 => ndvi_change_per_week = (0.2015 - 0.2208) / (3/7)
        self.assertAlmostEqual(ph["ndvi_change_per_week"], round((0.2015 - 0.2208) / (3.0 / 7.0), 4), places=4)

        # Minimum count (<4) & span (<21 days) gating
        short_pts = [(datetime(2026, 11, 1), 0.30), (datetime(2026, 11, 8), 0.40), (datetime(2026, 11, 15), 0.50)]
        ph_short = analyze_seasonal_phenology(short_pts, crop_type="Wheat")
        self.assertEqual(ph_short["stage_confidence"], "insufficient")
        self.assertEqual(ph_short["stage"], "Insufficient temporal evidence")

        # Multiple consecutive declines (>=2) with drop toward bare soil after peak triggers probable senescence/harvest
        sen_pts = [
            (datetime(2026, 9, 1), 0.35),
            (datetime(2026, 9, 15), 0.68),
            (datetime(2026, 10, 1), 0.52),
            (datetime(2026, 10, 15), 0.22),
        ]
        ph_sen = analyze_seasonal_phenology(sen_pts, crop_type="Soybean")
        self.assertEqual(ph_sen["consecutive_declines"], 2)
        self.assertIn("Senescence", ph_sen["stage"])


class TestPhase2APIsAndMigration(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.tmpdir.name, "test_phase2.db")
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
            farm = Farm(name="Phase2 Farm", center_lat=13.081, center_lng=77.591, total_area_ha=5.0)
            db.add(farm)
            db.commit()
            db.refresh(farm)
            field = Field(farm_id=farm.id, name="Test Plot", crop_type="Wheat", boundary_geojson=SAMPLE_POLYGON, area_ha=5.0)
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

    def test_dashboard_exposes_approximate_radar_timestamp_and_quality_separation(self):
        db = self.SessionLocal()
        s2 = SatelliteObservation(
            field_id=self.field_id,
            source="sentinel-2",
            collection_id="COPERNICUS/S2_SR_HARMONIZED",
            image_id="S2_EXACT_SCENE",
            acquisition_date=datetime(2026, 11, 15, 5, 10, 0),
            acquisition_day="2026-11-15",
            cloud_cover_pct=4.5,
            valid_pixel_pct=93.2,
            observation_count=2,
            composite_method="same_day_mgrs_mosaic",
            bands_metadata=json.dumps({"scale_m": 20}),
            status="processed",
            is_demo=False,
            is_superseded=False,
        )
        # Migrated legacy S1 row with approximate timestamp precision
        s1_approx = SatelliteObservation(
            field_id=self.field_id,
            source="sentinel-1",
            collection_id="COPERNICUS/S1_GRD",
            image_id=None,
            acquisition_date=datetime(2026, 11, 15, 0, 34, 6),
            acquisition_day="2026-11-15",
            cloud_cover_pct=None,
            bands_metadata=json.dumps({
                "migration_note": "Split Sentinel-1 indices out from legacy S2 observation 15",
                "timestamp_precision": "migrated_legacy_approximate_day",
            }),
            status="processed",
            is_demo=False,
            is_superseded=False,
        )
        db.add_all([s2, s1_approx])
        db.commit()
        db.add_all([
            IndexResult(observation_id=s2.id, index_type="NDVI", mean_value=0.45),
            IndexResult(observation_id=s1_approx.id, index_type="S1_VV", mean_value=-11.72),
            IndexResult(observation_id=s1_approx.id, index_type="S1_VH", mean_value=-21.52),
            IndexResult(observation_id=s1_approx.id, index_type="S1_RVI", mean_value=0.486),
        ])
        db.commit()
        db.close()

        dash = self.client.get(f"/api/fields/{self.field_id}/dashboard").json()
        self.assertEqual(dash["optical_timestamp_precision"], "exact")
        self.assertEqual(dash["radar_timestamp_precision"], "approximate")
        self.assertEqual(dash["optical_quality"]["valid_pixel_pct"], 93.2)
        self.assertEqual(dash["optical_quality"]["observation_count"], 2)
        self.assertEqual(dash["optical_quality"]["composite_method"], "same_day_mgrs_mosaic")
        self.assertEqual(dash["radar_quality"]["timestamp_precision"], "approximate")
        self.assertEqual(dash["radar_wetness_assessment"]["method"], "insufficient_same_orbit_baseline")
        self.assertIn("measured_inputs", dash["scientific_provenance"])
        self.assertIn("derived_indices", dash["scientific_provenance"])
        self.assertIn("heuristic_interpretations", dash["scientific_provenance"])

    def test_analyze_persists_composite_metadata_and_history_retains_gaps(self):
        fake_payload = {
            "is_demo": False,
            "optical_available": True,
            "radar_available": True,
            "source": "sentinel-2",
            "collection_id": "COPERNICUS/S2_SR_HARMONIZED",
            "image_id": "S2_20261120",
            "acquisition_date": datetime(2026, 11, 20, 5, 10, 0),
            "cloud_cover": 6.0,
            "valid_pixel_pct": 89.5,
            "observation_count": 2,
            "composite_method": "same_day_mgrs_mosaic",
            "bands_metadata": {"scale_m": 20},
            "ndvi_stats": {"NDVI_mean": 0.58},
            "evi_stats": {"EVI_mean": 0.44},
            "savi_stats": {"SAVI_mean": 0.42},
            "gndvi_stats": {"GNDVI_mean": 0.52},
            "ndmi_stats": {"NDMI_mean": 0.16},
            "ndre_stats": {"NDRE_mean": 0.29},
            "s1_stats": {
                "source": "sentinel-1",
                "collection_id": "COPERNICUS/S1_GRD",
                "image_id": "S1A_20261121",
                "orbit_pass": "DESCENDING",
                "relative_orbit": 63,
                "incidence_angle_deg": 38.4,
                "S1_VV": -10.1,
                "S1_VH": -16.4,
                "S1_RVI": 0.76,
                "baseline_vv_db": -12.6,
                "delta_vv_db": 2.5,
                "baseline_obs_count": 3,
                "orbit_consistent": True,
                "acquisition_date": datetime(2026, 11, 21, 18, 22, 0),
            },
            # Intentionally leave a 25-day gap between Oct 16 and Nov 10
            "time_series": [
                {
                    "source": "sentinel-2",
                    "collection_id": "COPERNICUS/S2_SR_HARMONIZED",
                    "image_id": "S2_COMP_1",
                    "acquisition_date": datetime(2026, 10, 16, 5, 10, 0),
                    "cloud_cover": 3.0,
                    "valid_pixel_pct": 92.0,
                    "observation_count": 2,
                    "composite_method": "10d_median_composite",
                    "composite_period_start": "2026-10-10",
                    "composite_period_end": "2026-10-19",
                    "NDVI": 0.32,
                    "NDMI": 0.02,
                    "NDRE": 0.15,
                },
                {
                    "source": "sentinel-2",
                    "collection_id": "COPERNICUS/S2_SR_HARMONIZED",
                    "image_id": "S2_COMP_2",
                    "acquisition_date": datetime(2026, 11, 10, 5, 10, 0),
                    "cloud_cover": 5.0,
                    "valid_pixel_pct": 84.0,
                    "observation_count": 3,
                    "composite_method": "10d_median_composite",
                    "composite_period_start": "2026-11-01",
                    "composite_period_end": "2026-11-10",
                    "NDVI": 0.49,
                    "NDMI": 0.11,
                    "NDRE": 0.24,
                },
            ],
            "time_series_gaps": [{"period_start": "2026-10-20", "period_end": "2026-10-31", "status": "missing_gap"}],
            "time_series_meta": {"window_days": 180, "bin_days": 10},
        }

        class _FakeGEE:
            def initialize(self):
                return True

            def analyze_field(self, boundary_geojson, start_date, end_date, cloud_max=20, zone_geoms=None):
                return fake_payload

        with patch("backend.api.satellite.get_gee_service", return_value=_FakeGEE()):
            res = self.client.post(f"/api/fields/{self.field_id}/analyze").json()
        self.assertEqual(res["time_series_gaps"], 1)

        hist = self.client.get(f"/api/fields/{self.field_id}/history").json()
        # Only the 3 real dates exist; the 25-day gap is NOT interpolated
        self.assertEqual(hist["dates"], ["2026-10-16", "2026-11-10", "2026-11-20"])
        self.assertEqual(len(hist["missing_gap_periods"]), 1)
        self.assertEqual(hist["missing_gap_periods"][0]["gap_days"], 25)
        self.assertEqual(hist["observations"][0]["composite_method"], "10d_median_composite")
        self.assertEqual(hist["observations"][0]["observation_count"], 2)
        self.assertEqual(hist["observations"][0]["valid_pixel_pct"], 92.0)
        self.assertEqual(hist["observations"][0]["timestamp_precision"], "composite_window")

        dash = self.client.get(f"/api/fields/{self.field_id}/dashboard").json()
        self.assertEqual(dash["radar_quality"]["incidence_angle_deg"], 38.4)
        self.assertEqual(dash["radar_quality"]["orbit_pass"], "DESCENDING")
        self.assertEqual(dash["radar_quality"]["relative_orbit"], 63)
        self.assertEqual(dash["radar_quality"]["delta_vv_db"], 2.5)
        self.assertEqual(dash["radar_timestamp_precision"], "exact")

    def test_phase2_sqlite_migration_is_idempotent(self):
        legacy = os.path.join(self.tmpdir.name, "p1.db")
        conn = sqlite3.connect(legacy)
        conn.execute("CREATE TABLE satellite_observations (id INTEGER PRIMARY KEY, field_id INTEGER)")
        conn.execute("INSERT INTO satellite_observations VALUES (1, 1)")
        conn.commit()
        conn.close()

        r1 = migrate_phase2_sqlite(legacy)
        self.assertEqual(r1["added_columns"], ["valid_pixel_pct", "observation_count", "composite_method"])
        r2 = migrate_phase2_sqlite(legacy)
        self.assertEqual(r2["added_columns"], [])


if __name__ == "__main__":
    unittest.main()
