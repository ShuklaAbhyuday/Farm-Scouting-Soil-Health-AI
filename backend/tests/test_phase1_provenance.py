import json
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from backend.database import Base, get_db
from backend.main import app
from backend.migrations.phase1_migration import migrate_sqlite_db
from backend.models.farm import Farm
from backend.models.field import Field
from backend.models.hotspot import Hotspot
from backend.models.satellite import IndexResult, SatelliteObservation

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


class FakeGEEService:
    """Configurable deterministic GEE double for Phase 1 provenance tests."""

    def __init__(self, payload: dict):
        self.payload = payload

    def initialize(self) -> bool:
        return True

    def analyze_field(self, boundary_geojson, start_date, end_date, cloud_max=20, zone_geoms=None):
        zone_stats = {}
        if zone_geoms and self.payload.get("optical_available", True):
            base_ndvi = (self.payload.get("ndvi_stats") or {}).get("NDVI_mean", 0.65)
            for idx in range(len(zone_geoms)):
                zone_stats[idx] = {
                    "NDVI": max(0.15, base_ndvi - (0.28 if idx == 0 else 0.0)),
                    "NDMI": 0.12 if idx != 0 else -0.10,
                    "NDRE": 0.20 if idx != 0 else 0.08,
                }
        out = dict(self.payload)
        out["zone_stats"] = zone_stats
        return out


class TestPhase1DatabaseAndProvenance(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.tmpdir.name, "test_phase1.db")
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
            farm = Farm(name="Test Farm", center_lat=13.081, center_lng=77.591, total_area_ha=4.8)
            db.add(farm)
            db.commit()
            db.refresh(farm)

            field = Field(
                farm_id=farm.id,
                name="North Plot",
                crop_type="wheat",
                boundary_geojson=SAMPLE_POLYGON,
                area_ha=4.8,
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

    def test_1_repeat_scans_do_not_create_duplicate_records(self):
        s2_dt = datetime(2026, 11, 12, 5, 10, 15)
        s1_dt = datetime(2026, 11, 14, 18, 22, 0)
        payload = {
            "is_demo": False,
            "optical_available": True,
            "radar_available": True,
            "source": "sentinel-2",
            "collection_id": "COPERNICUS/S2_SR_HARMONIZED",
            "image_id": "20261112T051015_20261112T052100_T43PGP",
            "acquisition_date": s2_dt,
            "cloud_cover": 2.5,
            "bands_metadata": {"scale_m": 10},
            "ndvi_stats": {"NDVI_mean": 0.64, "NDVI_min": 0.35, "NDVI_max": 0.78, "NDVI_stdDev": 0.08},
            "evi_stats": {"EVI_mean": 0.51},
            "savi_stats": {"SAVI_mean": 0.49},
            "gndvi_stats": {"GNDVI_mean": 0.57},
            "ndmi_stats": {"NDMI_mean": 0.19},
            "ndre_stats": {"NDRE_mean": 0.31},
            "s1_stats": {
                "source": "sentinel-1",
                "collection_id": "COPERNICUS/S1_GRD",
                "image_id": "S1A_IW_GRDH_1SDV_20261114T182200",
                "orbit_pass": "DESCENDING",
                "relative_orbit": 63,
                "acquisition_date": s1_dt,
                "S1_VV": -10.8,
                "S1_VH": -17.4,
                "S1_RVI": 0.72,
            },
            "time_series": [],
        }

        fake = FakeGEEService(payload)
        with patch("backend.api.satellite.get_gee_service", return_value=fake):
            r1 = self.client.post(f"/api/fields/{self.field_id}/analyze")
            r2 = self.client.post(f"/api/fields/{self.field_id}/analyze")

        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)

        db = self.SessionLocal()
        obs_all = db.query(SatelliteObservation).filter(SatelliteObservation.field_id == self.field_id).all()
        s2_obs = [o for o in obs_all if o.source == "sentinel-2" and not o.is_superseded]
        s1_obs = [o for o in obs_all if o.source == "sentinel-1" and not o.is_superseded]
        self.assertEqual(len(obs_all), 2)
        self.assertEqual(len(s2_obs), 1)
        self.assertEqual(len(s1_obs), 1)
        self.assertEqual(len(db.query(IndexResult).filter(IndexResult.observation_id == s2_obs[0].id).all()), 6)
        self.assertEqual(len(db.query(IndexResult).filter(IndexResult.observation_id == s1_obs[0].id).all()), 3)

        # Partial unique index uq_active_obs_per_day also rejects raw duplicate inserts at SQLite level
        dup = SatelliteObservation(
            field_id=self.field_id,
            source="sentinel-2",
            acquisition_date=s2_dt,
            acquisition_day="2026-11-12",
            is_demo=False,
            is_superseded=False,
        )
        db.add(dup)
        with self.assertRaises(IntegrityError):
            db.commit()
        db.rollback()
        db.close()

    def test_2_sentinel1_and_sentinel2_timestamps_and_provenance_stay_independent(self):
        s2_dt = datetime(2026, 11, 10, 5, 11, 42)
        s1_dt = datetime(2026, 11, 13, 18, 25, 9)
        payload = {
            "is_demo": False,
            "optical_available": True,
            "radar_available": True,
            "source": "sentinel-2",
            "collection_id": "COPERNICUS/S2_SR_HARMONIZED",
            "image_id": "S2_SCENE_20261110",
            "acquisition_date": s2_dt,
            "cloud_cover": 1.2,
            "bands_metadata": {"scale_m": 10},
            "ndvi_stats": {"NDVI_mean": 0.61},
            "evi_stats": {"EVI_mean": 0.48},
            "savi_stats": {"SAVI_mean": 0.46},
            "gndvi_stats": {"GNDVI_mean": 0.55},
            "ndmi_stats": {"NDMI_mean": 0.14},
            "ndre_stats": {"NDRE_mean": 0.28},
            "s1_stats": {
                "source": "sentinel-1",
                "collection_id": "COPERNICUS/S1_GRD",
                "image_id": "S1A_SCENE_20261113",
                "orbit_pass": "ASCENDING",
                "relative_orbit": 114,
                "acquisition_date": s1_dt,
                "S1_VV": -9.9,
                "S1_VH": -16.2,
                "S1_RVI": 0.78,
            },
            "time_series": [],
        }

        with patch("backend.api.satellite.get_gee_service", return_value=FakeGEEService(payload)):
            res = self.client.post(f"/api/fields/{self.field_id}/analyze")
        self.assertEqual(res.status_code, 200)

        db = self.SessionLocal()
        s2 = db.query(SatelliteObservation).filter_by(field_id=self.field_id, source="sentinel-2").one()
        s1 = db.query(SatelliteObservation).filter_by(field_id=self.field_id, source="sentinel-1").one()
        self.assertEqual(s2.acquisition_date, s2_dt)
        self.assertEqual(s1.acquisition_date, s1_dt)
        self.assertNotEqual(s2.acquisition_day, s1.acquisition_day)
        self.assertEqual(s2.collection_id, "COPERNICUS/S2_SR_HARMONIZED")
        self.assertEqual(s2.image_id, "S2_SCENE_20261110")
        self.assertEqual(s1.collection_id, "COPERNICUS/S1_GRD")
        self.assertEqual(s1.image_id, "S1A_SCENE_20261113")
        self.assertIsNone(s1.cloud_cover_pct)
        db.close()

        dash = self.client.get(f"/api/fields/{self.field_id}/dashboard").json()
        self.assertEqual(dash["optical_source"], "sentinel-2")
        self.assertEqual(dash["radar_source"], "sentinel-1")
        self.assertTrue(dash["latest_observation_date"].startswith("2026-11-10T05:11:42"))
        self.assertTrue(dash["radar_observation_date"].startswith("2026-11-13T18:25:09"))
        self.assertEqual(dash["s1_vv"], -9.9)
        self.assertFalse(dash["is_demo"])

    def test_3_missing_optical_data_stores_null_no_fabricated_zeros_or_multipliers(self):
        # Case A: Radar-only acquisition (no Sentinel-2 optical scene passed cloud threshold)
        radar_only_payload = {
            "is_demo": False,
            "optical_available": False,
            "radar_available": True,
            "acquisition_date": datetime(2026, 11, 15, 18, 10, 0),
            "s1_stats": {
                "source": "sentinel-1",
                "collection_id": "COPERNICUS/S1_GRD",
                "image_id": "S1B_CLOUDY_WEEK",
                "orbit_pass": "DESCENDING",
                "relative_orbit": 63,
                "acquisition_date": datetime(2026, 11, 15, 18, 10, 0),
                "S1_VV": -11.4,
                "S1_VH": -18.0,
                "S1_RVI": 0.69,
            },
            "time_series": [],
        }
        with patch("backend.api.satellite.get_gee_service", return_value=FakeGEEService(radar_only_payload)):
            res = self.client.post(f"/api/fields/{self.field_id}/analyze")
        self.assertEqual(res.status_code, 200)

        db = self.SessionLocal()
        self.assertEqual(db.query(SatelliteObservation).filter_by(field_id=self.field_id, source="sentinel-2").count(), 0)
        self.assertEqual(db.query(SatelliteObservation).filter_by(field_id=self.field_id, source="sentinel-1").count(), 1)
        db.close()

        # Case B: Partial optical observation where EVI/SAVI/GNDVI are None -> must remain NULL / absent, NEVER 0.0 or ndvi*0.88
        partial_s2_payload = {
            "is_demo": False,
            "optical_available": True,
            "radar_available": False,
            "source": "sentinel-2",
            "collection_id": "COPERNICUS/S2_SR_HARMONIZED",
            "image_id": "S2_PARTIAL_SCENE",
            "acquisition_date": datetime(2026, 11, 16, 5, 10, 0),
            "cloud_cover": 8.0,
            "ndvi_stats": {"NDVI_mean": 0.50},
            "evi_stats": None,
            "savi_stats": None,
            "gndvi_stats": None,
            "ndmi_stats": {"NDMI_mean": 0.11},
            "ndre_stats": None,
            "s1_stats": None,
            "time_series": [
                {
                    "source": "sentinel-2",
                    "collection_id": "COPERNICUS/S2_SR_HARMONIZED",
                    "image_id": "S2_HIST_1",
                    "acquisition_date": datetime(2026, 10, 25, 5, 10, 0),
                    "cloud_cover": 5.0,
                    "NDVI": 0.42,
                    "EVI": None,
                    "SAVI": None,
                    "GNDVI": None,
                    "NDMI": 0.08,
                    "NDRE": None,
                }
            ],
        }
        with patch("backend.api.satellite.get_gee_service", return_value=FakeGEEService(partial_s2_payload)):
            res2 = self.client.post(f"/api/fields/{self.field_id}/analyze")
        self.assertEqual(res2.status_code, 200)

        dash = self.client.get(f"/api/fields/{self.field_id}/dashboard").json()
        self.assertEqual(dash["ndvi_mean"], 0.5)
        self.assertIsNone(dash["evi_mean"])
        self.assertIsNone(dash["savi_mean"])
        self.assertIsNone(dash["gndvi_mean"])
        self.assertIsNone(dash["ndre_mean"])

        history = self.client.get(f"/api/fields/{self.field_id}/history").json()
        self.assertEqual(len(history["observations"]), 2)
        for pt in history["observations"]:
            self.assertIsNone(pt["evi"])
            self.assertIsNone(pt["savi"])
            self.assertIsNone(pt["gndvi"])
            self.assertIsNone(pt["ndre"])

    def test_4_historical_observations_and_hotspots_preserved_across_scans(self):
        scan1 = {
            "is_demo": False,
            "optical_available": True,
            "radar_available": False,
            "source": "sentinel-2",
            "collection_id": "COPERNICUS/S2_SR_HARMONIZED",
            "image_id": "S2_DAY1",
            "acquisition_date": datetime(2026, 11, 1, 5, 10, 0),
            "cloud_cover": 3.0,
            "ndvi_stats": {"NDVI_mean": 0.55},
            "ndmi_stats": {"NDMI_mean": 0.12},
            "ndre_stats": {"NDRE_mean": 0.25},
            "time_series": [],
        }
        scan2 = {
            "is_demo": False,
            "optical_available": True,
            "radar_available": False,
            "source": "sentinel-2",
            "collection_id": "COPERNICUS/S2_SR_HARMONIZED",
            "image_id": "S2_DAY2",
            "acquisition_date": datetime(2026, 11, 11, 5, 10, 0),
            "cloud_cover": 1.0,
            "ndvi_stats": {"NDVI_mean": 0.68},
            "ndmi_stats": {"NDMI_mean": 0.22},
            "ndre_stats": {"NDRE_mean": 0.34},
            "time_series": [],
        }

        with patch("backend.api.satellite.get_gee_service", return_value=FakeGEEService(scan1)):
            self.client.post(f"/api/fields/{self.field_id}/analyze")

        db = self.SessionLocal()
        day1_obs = db.query(SatelliteObservation).filter_by(field_id=self.field_id, acquisition_day="2026-11-01").one()
        day1_hs_ids = {h.id for h in db.query(Hotspot).filter_by(field_id=self.field_id).all()}
        self.assertGreater(len(day1_hs_ids), 0)
        db.close()

        with patch("backend.api.satellite.get_gee_service", return_value=FakeGEEService(scan2)):
            self.client.post(f"/api/fields/{self.field_id}/analyze")

        db = self.SessionLocal()
        # Historical observation & its NDVI remained untouched
        day1_obs_after = db.query(SatelliteObservation).filter_by(id=day1_obs.id).one()
        self.assertEqual(day1_obs_after.image_id, "S2_DAY1")
        day1_ndvi = db.query(IndexResult).filter_by(observation_id=day1_obs.id, index_type="NDVI").one()
        self.assertEqual(day1_ndvi.mean_value, 0.55)

        # Historical hotspots were NOT deleted; they were archived (is_active=False)
        old_hs = db.query(Hotspot).filter(Hotspot.id.in_(day1_hs_ids)).all()
        self.assertEqual(len(old_hs), len(day1_hs_ids))
        self.assertTrue(all(h.is_active is False for h in old_hs))

        new_active_hs = db.query(Hotspot).filter_by(field_id=self.field_id, is_active=True).all()
        self.assertGreater(len(new_active_hs), 0)
        self.assertTrue(all(h.observation_id != day1_obs.id for h in new_active_hs))
        db.close()

        # API exposes active hotspots by default and archived+active when include_historical=true
        active_resp = self.client.get(f"/api/fields/{self.field_id}/hotspots").json()
        all_resp = self.client.get(f"/api/fields/{self.field_id}/hotspots?include_historical=true").json()
        self.assertEqual(len(active_resp), len(new_active_hs))
        self.assertEqual(len(all_resp), len(day1_hs_ids) + len(new_active_hs))

    def test_5_demo_observations_never_contaminate_real_satellite_phenology(self):
        db = self.SessionLocal()
        # Inject an extreme Demo simulation point (NDVI = 0.96) alongside real S2 points (NDVI = 0.44, 0.62)
        demo_obs = SatelliteObservation(
            field_id=self.field_id,
            source="demo-simulation",
            collection_id="DEMO/SIMULATED",
            image_id="demo_20260815",
            acquisition_date=datetime(2026, 8, 15, 10, 0, 0),
            acquisition_day="2026-08-15",
            cloud_cover_pct=4.2,
            status="processed",
            is_demo=True,
            is_superseded=False,
        )
        real_obs_1 = SatelliteObservation(
            field_id=self.field_id,
            source="sentinel-2",
            collection_id="COPERNICUS/S2_SR_HARMONIZED",
            image_id="real_20261101",
            acquisition_date=datetime(2026, 11, 1, 5, 10, 0),
            acquisition_day="2026-11-01",
            cloud_cover_pct=2.0,
            status="processed",
            is_demo=False,
            is_superseded=False,
        )
        real_obs_2 = SatelliteObservation(
            field_id=self.field_id,
            source="sentinel-2",
            collection_id="COPERNICUS/S2_SR_HARMONIZED",
            image_id="real_20261111",
            acquisition_date=datetime(2026, 11, 11, 5, 10, 0),
            acquisition_day="2026-11-11",
            cloud_cover_pct=1.0,
            status="processed",
            is_demo=False,
            is_superseded=False,
        )
        db.add_all([demo_obs, real_obs_1, real_obs_2])
        db.commit()
        db.add_all([
            IndexResult(observation_id=demo_obs.id, index_type="NDVI", mean_value=0.96),
            IndexResult(observation_id=real_obs_1.id, index_type="NDVI", mean_value=0.44),
            IndexResult(observation_id=real_obs_2.id, index_type="NDVI", mean_value=0.62),
        ])
        db.commit()
        db.close()

        dash = self.client.get(f"/api/fields/{self.field_id}/dashboard").json()
        self.assertFalse(dash["is_demo"])
        self.assertEqual(dash["optical_source"], "sentinel-2")
        self.assertEqual(dash["ndvi_mean"], 0.62)
        self.assertEqual(dash["phenology"]["observation_count"], 2)
        self.assertEqual(dash["phenology"]["peak_ndvi"], 0.62)
        self.assertNotEqual(dash["phenology"]["peak_ndvi"], 0.96)

        history = self.client.get(f"/api/fields/{self.field_id}/history").json()
        self.assertEqual(len(history["observations"]), 2)
        self.assertTrue(all(o["source"] == "sentinel-2" and not o["is_demo"] for o in history["observations"]))

    def test_6_legacy_migration_honesty_dedup_and_s1_split(self):
        legacy_db = os.path.join(self.tmpdir.name, "legacy.db")
        conn = sqlite3.connect(legacy_db)
        cur = conn.cursor()
        cur.execute("CREATE TABLE fields (id INTEGER PRIMARY KEY, name TEXT)")
        cur.execute("INSERT INTO fields VALUES (1, 'F1')")
        cur.execute("""
            CREATE TABLE satellite_observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                field_id INTEGER,
                source VARCHAR DEFAULT 'sentinel-2',
                collection_id VARCHAR,
                image_id VARCHAR,
                acquisition_date DATETIME NOT NULL,
                cloud_cover_pct FLOAT,
                bands_metadata TEXT,
                status VARCHAR DEFAULT 'pending',
                processed_at DATETIME,
                created_at DATETIME
            )
        """)
        cur.execute("""
            CREATE TABLE index_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                observation_id INTEGER,
                index_type VARCHAR NOT NULL,
                mean_value FLOAT NOT NULL,
                min_value FLOAT,
                max_value FLOAT,
                std_value FLOAT,
                raster_data TEXT,
                statistics TEXT,
                created_at DATETIME
            )
        """)
        cur.execute("""
            CREATE TABLE hotspots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                field_id INTEGER,
                observation_id INTEGER
            )
        """)
        # Legacy Demo duplicates on 2026-08-19 + Mixed S2/S1 row on 2026-11-15
        cur.execute("INSERT INTO satellite_observations (id, field_id, source, acquisition_date, cloud_cover_pct, status, created_at) VALUES (1, 1, 'sentinel-2', '2026-08-19 21:00:00', 1.5, 'processed', '2026-08-20 21:00:00')")
        cur.execute("INSERT INTO satellite_observations (id, field_id, source, acquisition_date, cloud_cover_pct, status, created_at) VALUES (2, 1, 'sentinel-2', '2026-08-19 21:05:00', 4.2, 'processed', '2026-08-20 21:05:00')")
        cur.execute("INSERT INTO satellite_observations (id, field_id, source, acquisition_date, cloud_cover_pct, status, created_at) VALUES (15, 1, 'sentinel-2', '2026-11-15 00:34:06', 0.0, 'processed', '2026-11-25 21:43:29')")
        cur.execute("INSERT INTO index_results (observation_id, index_type, mean_value) VALUES (1, 'NDVI', 0.71)")
        cur.execute("INSERT INTO index_results (observation_id, index_type, mean_value) VALUES (2, 'NDVI', 0.72)")
        cur.execute("INSERT INTO index_results (observation_id, index_type, mean_value) VALUES (15, 'NDVI', 0.50)")
        cur.execute("INSERT INTO index_results (observation_id, index_type, mean_value) VALUES (15, 'S1_VV', -11.2)")
        cur.execute("INSERT INTO hotspots (id, field_id, observation_id) VALUES (1, 1, 15)")
        conn.commit()
        conn.close()

        rep = migrate_sqlite_db(legacy_db)
        self.assertEqual(rep["demo_migrated_ids"], [1, 2])
        self.assertEqual(rep["superseded_duplicate_ids"], [1])
        self.assertEqual(len(rep["split_s1_from_s2_ids"]), 1)
        self.assertEqual(rep["ambiguous_rows"], [])

        # Second run is idempotent
        rep2 = migrate_sqlite_db(legacy_db)
        self.assertEqual(rep2["demo_migrated_ids"], [])
        self.assertEqual(rep2["superseded_duplicate_ids"], [])
        self.assertEqual(rep2["split_s1_from_s2_ids"], [])

        conn = sqlite3.connect(legacy_db)
        conn.row_factory = sqlite3.Row
        rows = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM satellite_observations").fetchall()}
        self.assertEqual(rows[1]["source"], "demo-simulation")
        self.assertEqual(rows[1]["is_demo"], 1)
        self.assertEqual(rows[1]["is_superseded"], 1)
        self.assertEqual(rows[2]["source"], "demo-simulation")
        self.assertEqual(rows[2]["is_superseded"], 0)
        s1_id = rep["split_s1_from_s2_ids"][0]["to_s1_obs"]
        self.assertEqual(rows[s1_id]["source"], "sentinel-1")
        self.assertIsNone(rows[s1_id]["cloud_cover_pct"])
        hs_active = conn.execute("SELECT is_active FROM hotspots WHERE id=1").fetchone()[0]
        self.assertEqual(hs_active, 1)
        conn.close()


if __name__ == "__main__":
    unittest.main()
