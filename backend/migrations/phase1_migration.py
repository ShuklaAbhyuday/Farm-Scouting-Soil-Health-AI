"""Phase 1 safe, idempotent SQLite schema & provenance migration."""
from __future__ import annotations

import json
import sqlite3
from typing import Any


S1_INDEX_TYPES = {"S1_VV", "S1_VH", "S1_RVI"}


def _get_columns(conn: sqlite3.Connection, table: str) -> dict[str, dict[str, Any]]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {
        r[1]: {"cid": r[0], "name": r[1], "type": r[2], "notnull": bool(r[3]), "default": r[4], "pk": bool(r[5])}
        for r in rows
    }


def _classify_legacy_observation(obs_row: tuple) -> tuple[str, bool, str | None, dict]:
    """
    Honestly classify historical rows without fabricating missing provenance.
    obs_row: (id, field_id, source, collection_id, image_id, acquisition_date, cloud_cover_pct, bands_metadata, status, processed_at, created_at)
    """
    obs_id, _fid, source, coll_id, img_id, acq_date, cloud_pct, bands_meta, _status, _proc_at, created_at = obs_row

    existing_meta = {}
    if bands_meta:
        try:
            existing_meta = json.loads(bands_meta)
        except Exception:
            existing_meta = {"raw_legacy_metadata": bands_meta}

    if source == "demo-simulation":
        return "demo-simulation", True, coll_id or "DEMO/SIMULATED", existing_meta
    if source == "sentinel-1":
        return "sentinel-1", False, coll_id or "COPERNICUS/S1_GRD", existing_meta

    # Pre-2026-11-24 rows in farm_scout.db were generated while DEMO_MODE=True was hardcoded
    created_str = str(created_at or "")
    acq_str = str(acq_date or "")
    if created_str.startswith("2026-08-"):
        existing_meta.setdefault("migration_note", "Classified as demo-simulation: created 2026-08 when DEMO_MODE=True was hardcoded")
        return "demo-simulation", True, "DEMO/SIMULATED", existing_meta

    # Real Sentinel-2 rows from 2026-11-24 onward (GEE overpass timestamps & 6-decimal cloud cover)
    if created_str >= "2026-11-24" or acq_str.startswith("2024-"):
        existing_meta.setdefault("migration_note", "Legacy GEE Sentinel-2 row migrated without original image_id")
        return "sentinel-2", False, coll_id or "COPERNICUS/S2_SR_HARMONIZED", existing_meta

    # Ambiguous fallback: preserve source honestly and tag uncertainty
    existing_meta.setdefault("migration_note", "Provenance ambiguous; preserved without relabeling")
    return source or "sentinel-2", False, coll_id, existing_meta


def migrate_sqlite_db(db_path: str) -> dict[str, Any]:
    """Execute idempotent Phase 1 migration on an existing SQLite database file."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = None
    report: dict[str, Any] = {
        "ambiguous_rows": [],
        "demo_migrated_ids": [],
        "superseded_duplicate_ids": [],
        "split_s1_from_s2_ids": [],
    }

    try:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "satellite_observations" not in tables:
            return report

        obs_cols = _get_columns(conn, "satellite_observations")
        idx_cols = _get_columns(conn, "index_results") if "index_results" in tables else {}
        hs_cols = _get_columns(conn, "hotspots") if "hotspots" in tables else {}

        needs_obs_rebuild = (
            "acquisition_day" not in obs_cols
            or "is_demo" not in obs_cols
            or "is_superseded" not in obs_cols
            or obs_cols.get("cloud_cover_pct", {}).get("notnull", False)
        )
        needs_idx_rebuild = any(
            idx_cols.get(col, {}).get("notnull", False)
            for col in ("mean_value", "min_value", "max_value", "std_value")
        )

        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("BEGIN")

        # 1. Add is_active to hotspots if missing (preserve all historical rows)
        if "hotspots" in tables and "is_active" not in hs_cols:
            conn.execute("ALTER TABLE hotspots ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1")

        # 2. Rebuild index_results with nullable stat columns preserving all IDs
        if needs_idx_rebuild:
            conn.execute(
                """
                CREATE TABLE index_results_new (
                    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                    observation_id INTEGER,
                    index_type VARCHAR NOT NULL,
                    mean_value FLOAT,
                    min_value FLOAT,
                    max_value FLOAT,
                    std_value FLOAT,
                    raster_data TEXT,
                    statistics TEXT,
                    created_at DATETIME,
                    FOREIGN KEY(observation_id) REFERENCES satellite_observations (id)
                )
                """
            )
            conn.execute(
                """
                INSERT INTO index_results_new (
                    id, observation_id, index_type, mean_value, min_value, max_value, std_value,
                    raster_data, statistics, created_at
                )
                SELECT id, observation_id, index_type, mean_value, min_value, max_value, std_value,
                       raster_data, statistics, created_at
                FROM index_results
                """
            )
            conn.execute("DROP TABLE index_results")
            conn.execute("ALTER TABLE index_results_new RENAME TO index_results")
            conn.execute("CREATE INDEX IF NOT EXISTS ix_index_results_id ON index_results (id)")

        # 3. Rebuild satellite_observations with provenance columns & nullable cloud_cover_pct
        if needs_obs_rebuild:
            legacy_rows = conn.execute(
                """
                SELECT id, field_id, source, collection_id, image_id, acquisition_date,
                       cloud_cover_pct, bands_metadata, status, processed_at, created_at
                FROM satellite_observations
                ORDER BY id ASC
                """
            ).fetchall()

            conn.execute(
                """
                CREATE TABLE satellite_observations_new (
                    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                    field_id INTEGER,
                    source VARCHAR NOT NULL DEFAULT 'sentinel-2',
                    collection_id VARCHAR,
                    image_id VARCHAR,
                    acquisition_date DATETIME NOT NULL,
                    acquisition_day VARCHAR NOT NULL,
                    cloud_cover_pct FLOAT,
                    bands_metadata TEXT,
                    status VARCHAR DEFAULT 'pending',
                    is_demo BOOLEAN NOT NULL DEFAULT 0,
                    is_superseded BOOLEAN NOT NULL DEFAULT 0,
                    processed_at DATETIME,
                    created_at DATETIME,
                    FOREIGN KEY(field_id) REFERENCES fields (id)
                )
                """
            )

            # Track active (field_id, source, day) -> latest id to flag older duplicates as is_superseded=1
            seen_latest: dict[tuple[int, str, str], int] = {}
            prepared_rows = []
            for row in legacy_rows:
                obs_id, fid, _src, _coll, img_id, acq_date, cloud_pct, _meta, status, proc_at, created_at = row
                new_source, is_demo, new_coll, meta_dict = _classify_legacy_observation(row)
                if is_demo:
                    report["demo_migrated_ids"].append(obs_id)
                if "Provenance ambiguous" in meta_dict.get("migration_note", ""):
                    report["ambiguous_rows"].append(obs_id)

                acq_day = str(acq_date)[:10]
                key = (fid, new_source, acq_day)
                seen_latest[key] = obs_id  # iterating in ASC id order keeps highest id active
                prepared_rows.append((
                    obs_id, fid, new_source, new_coll, img_id, acq_date, acq_day,
                    None if new_source == "sentinel-1" else cloud_pct,
                    json.dumps(meta_dict),
                    status,
                    1 if is_demo else 0,
                    0,  # placeholder for is_superseded
                    proc_at,
                    created_at,
                ))

            for prow in prepared_rows:
                obs_id, fid, new_source, new_coll, img_id, acq_date, acq_day, cloud_pct, meta_json, status, is_demo, _sup, proc_at, created_at = prow
                is_sup = 1 if seen_latest[(fid, new_source, acq_day)] != obs_id else 0
                if is_sup:
                    report["superseded_duplicate_ids"].append(obs_id)
                conn.execute(
                    """
                    INSERT INTO satellite_observations_new (
                        id, field_id, source, collection_id, image_id, acquisition_date,
                        acquisition_day, cloud_cover_pct, bands_metadata, status,
                        is_demo, is_superseded, processed_at, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        obs_id, fid, new_source, new_coll, img_id, acq_date,
                        acq_day, cloud_pct, meta_json, status,
                        is_demo, is_sup, proc_at, created_at,
                    ),
                )

            conn.execute("DROP TABLE satellite_observations")
            conn.execute("ALTER TABLE satellite_observations_new RENAME TO satellite_observations")
            conn.execute("CREATE INDEX IF NOT EXISTS ix_satellite_observations_id ON satellite_observations (id)")

        # 4. Separate any Sentinel-1 indices (S1_VV/VH/RVI) that were attached to a Sentinel-2 observation
        mixed_s2_obs = conn.execute(
            """
            SELECT DISTINCT so.id, so.field_id, so.acquisition_date, so.acquisition_day,
                            so.status, so.is_demo, so.processed_at, so.created_at
            FROM satellite_observations so
            JOIN index_results ir ON ir.observation_id = so.id
            WHERE so.source != 'sentinel-1' AND ir.index_type IN ('S1_VV', 'S1_VH', 'S1_RVI')
            """
        ).fetchall()

        for so_id, fid, acq_date, acq_day, status, is_demo, proc_at, created_at in mixed_s2_obs:
            s1_source = "demo-simulation" if is_demo else "sentinel-1"
            s1_coll = "DEMO/SIMULATED" if is_demo else "COPERNICUS/S1_GRD"
            s1_meta = json.dumps({
                "migration_note": f"Split Sentinel-1 indices out from legacy S2 observation {so_id}; exact S1 overpass timestamp not recorded at original ingest",
                "timestamp_precision": "migrated_legacy_approximate_day",
            })
            # Check if an active S1 row already exists for same field/day
            existing_s1 = conn.execute(
                """
                SELECT id FROM satellite_observations
                WHERE field_id = ? AND source = ? AND acquisition_day = ? AND is_superseded = 0
                """,
                (fid, s1_source, acq_day),
            ).fetchone()

            if existing_s1:
                target_s1_id = existing_s1[0]
            else:
                cur = conn.execute(
                    """
                    INSERT INTO satellite_observations (
                        field_id, source, collection_id, image_id, acquisition_date,
                        acquisition_day, cloud_cover_pct, bands_metadata, status,
                        is_demo, is_superseded, processed_at, created_at
                    ) VALUES (?, ?, ?, NULL, ?, ?, NULL, ?, ?, ?, 0, ?, ?)
                    """,
                    (fid, s1_source, s1_coll, acq_date, acq_day, s1_meta, status, is_demo, proc_at, created_at),
                )
                target_s1_id = cur.lastrowid

            conn.execute(
                """
                UPDATE index_results
                SET observation_id = ?
                WHERE observation_id = ? AND index_type IN ('S1_VV', 'S1_VH', 'S1_RVI')
                """,
                (target_s1_id, so_id),
            )
            report["split_s1_from_s2_ids"].append({"from_s2_obs": so_id, "to_s1_obs": target_s1_id})

        # 5. Enforce partial unique index on active observations per (field, sensor, day)
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_active_obs_per_day
            ON satellite_observations (field_id, source, acquisition_day)
            WHERE is_superseded = 0
            """
        )

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.close()

    return report
