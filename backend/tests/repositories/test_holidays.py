from pathlib import Path

from backend.db import connect, initialize_database
from backend.repositories.holidays import (
    get_holiday_cache,
    list_holiday_cache,
    replace_holiday_cache,
    set_holiday_cache,
)


def test_holiday_cache_round_trip_and_replace(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    initialize_database(db_path)
    conn = connect(db_path)
    try:
        payload = {"01-01": {"name": "元旦", "isOffDay": True}}
        set_holiday_cache(conn, 2026, payload, "2026-01-01T00:00:00Z")
        assert get_holiday_cache(conn, 2026) == (
            payload,
            "2026-01-01T00:00:00Z",
        )

        replace_holiday_cache(
            conn,
            {
                "2027": {
                    "holidays": {},
                    "fetchedAt": "2027-01-01T00:00:00Z",
                }
            },
        )
        assert get_holiday_cache(conn, 2026) is None
        assert list_holiday_cache(conn) == {
            "2027": {
                "holidays": {},
                "fetchedAt": "2027-01-01T00:00:00Z",
            }
        }
    finally:
        conn.close()
