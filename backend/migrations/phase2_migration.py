"""Phase 2 idempotent additive SQLite migration for observation quality & composite provenance."""
from __future__ import annotations

import sqlite3
from typing import Any


def migrate_phase2_sqlite(db_path: str) -> dict[str, Any]:
    """Safely add nullable Phase 2 quality/composite columns without touching existing data."""
    conn = sqlite3.connect(db_path)
    report: dict[str, Any] = {"added_columns": []}
    try:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "satellite_observations" not in tables:
            return report

        existing = {r[1] for r in conn.execute("PRAGMA table_info(satellite_observations)").fetchall()}
        additions = [
            ("valid_pixel_pct", "FLOAT"),
            ("observation_count", "INTEGER"),
            ("composite_method", "VARCHAR"),
        ]
        for col_name, col_type in additions:
            if col_name not in existing:
                conn.execute(f"ALTER TABLE satellite_observations ADD COLUMN {col_name} {col_type}")
                report["added_columns"].append(col_name)
        conn.commit()
    finally:
        conn.close()
    return report
