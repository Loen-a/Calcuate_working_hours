from pathlib import Path

from backend.db import connect, initialize_database
from backend.repositories.entries import (
    delete_entry,
    list_entries,
    replace_entries,
    upsert_entry,
)


def test_entry_upsert_delete_and_replace(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    initialize_database(db_path)
    conn = connect(db_path)
    try:
        upsert_entry(conn, "2026-07-12", "08:00", "18:30", True)
        upsert_entry(conn, "2026-07-12", "08:10", "18:40", None)
        assert list_entries(conn) == {
            "2026-07-12": {"in": "08:10", "out": "18:40"}
        }

        replace_entries(
            conn,
            {
                "2026-07-13": {
                    "in": "08:00",
                    "out": "18:00",
                    "counts": False,
                }
            },
        )
        assert list_entries(conn) == {
            "2026-07-13": {
                "in": "08:00",
                "out": "18:00",
                "counts": False,
            }
        }
        assert delete_entry(conn, "2026-07-13") is True
        assert delete_entry(conn, "2026-07-13") is False
    finally:
        conn.close()
