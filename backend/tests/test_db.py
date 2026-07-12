import sqlite3
from pathlib import Path

from backend.db import SCHEMA_VERSION, connect, initialize_database


def test_initialize_database_creates_schema_and_default_theme(tmp_path: Path) -> None:
    db_path = tmp_path / "workhours.db"
    initialize_database(db_path)

    conn = connect(db_path)
    try:
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        theme = conn.execute(
            "SELECT theme FROM preferences WHERE id = 1"
        ).fetchone()["theme"]
    finally:
        conn.close()

    assert tables >= {"work_entries", "preferences", "holiday_cache"}
    assert version == SCHEMA_VERSION == 1
    assert theme == "cool"


def test_initialize_database_rejects_newer_schema(tmp_path: Path) -> None:
    db_path = tmp_path / "workhours.db"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA user_version = 99")
    conn.close()

    try:
        initialize_database(db_path)
    except RuntimeError as exc:
        assert "schema version 99" in str(exc)
    else:
        raise AssertionError("newer schema should be rejected")
