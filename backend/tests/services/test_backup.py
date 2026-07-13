import sqlite3
from pathlib import Path

import pytest

from backend.db import connect, initialize_database
from backend.repositories.entries import list_entries, upsert_entry
from backend.repositories.holidays import list_holiday_cache, set_holiday_cache
from backend.repositories.preferences import get_theme, set_theme
from backend.services.backup import build_backup, restore_backup


def _version_2_backup() -> dict[str, object]:
    return {
        "version": 2,
        "exportedAt": "2026-07-12T00:00:00Z",
        "entries": {},
        "preferences": {"theme": "cool"},
        "holidayCache": {},
    }


def test_version_1_replaces_only_entries(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    initialize_database(db_path)
    conn = connect(db_path)
    with conn:
        set_theme(conn, "teal")
        upsert_entry(conn, "2026-07-01", "08:00", "18:00", True)
        set_holiday_cache(
            conn,
            2026,
            {"01-01": {"name": "New Year", "isOffDay": True}},
            "2026-01-01T00:00:00Z",
        )

    summary = restore_backup(
        conn,
        {
            "version": 1,
            "exportedAt": "2026-07-12T00:00:00Z",
            "entries": {
                "2026-07-12": {"in": "08:10", "out": "18:40"}
            },
        },
    )

    assert summary == {"version": 1, "entries": 1, "holidayYears": 0}
    assert list_entries(conn) == {
        "2026-07-12": {"in": "08:10", "out": "18:40"}
    }
    assert get_theme(conn) == "teal"
    assert list_holiday_cache(conn) == {
        "2026": {
            "holidays": {"01-01": {"name": "New Year", "isOffDay": True}},
            "fetchedAt": "2026-01-01T00:00:00Z",
        }
    }
    conn.close()


def test_version_2_round_trip_and_invalid_restore_is_atomic(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "test.db"
    initialize_database(db_path)
    conn = connect(db_path)
    original = build_backup(conn)
    original["entries"] = {
        "2026-07-12": {"in": "08:00", "out": "18:30", "counts": True}
    }
    original["preferences"] = {"theme": "teal"}

    restore_backup(conn, original)
    before_invalid = build_backup(conn)
    bad = {
        **before_invalid,
        "entries": {"2026-07-13": {"in": "18:00", "out": "08:00"}},
    }
    with pytest.raises(ValueError):
        restore_backup(conn, bad)

    assert build_backup(conn)["entries"] == before_invalid["entries"]
    assert build_backup(conn)["preferences"] == {"theme": "teal"}
    assert build_backup(conn)["holidayCache"] == before_invalid["holidayCache"]
    conn.close()


def test_version_2_write_failure_rolls_back_all_categories(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "test.db"
    initialize_database(db_path)
    conn = connect(db_path)
    with conn:
        upsert_entry(conn, "2026-07-01", "08:00", "18:00", True)
        set_theme(conn, "cool")
        set_holiday_cache(
            conn,
            2026,
            {"01-01": {"name": "New Year", "isOffDay": True}},
            "2026-01-01T00:00:00Z",
        )
        conn.execute(
            """
            CREATE TRIGGER reject_teal_theme
            BEFORE UPDATE ON preferences
            WHEN NEW.theme = 'teal'
            BEGIN
                SELECT RAISE(ABORT, 'simulated write failure');
            END
            """
        )

    before = build_backup(conn)
    backup = {
        **before,
        "entries": {"2026-07-12": {"in": "08:10", "out": "18:40"}},
        "preferences": {"theme": "teal"},
        "holidayCache": {},
    }

    with pytest.raises(sqlite3.IntegrityError, match="simulated write failure"):
        restore_backup(conn, backup)

    assert list_entries(conn) == before["entries"]
    assert get_theme(conn) == before["preferences"]["theme"]
    assert list_holiday_cache(conn) == before["holidayCache"]
    conn.close()


@pytest.mark.parametrize("version", [True, False, 1.0, 2.0, "1", "2"])
def test_restore_rejects_non_integer_versions(
    tmp_path: Path,
    version: object,
) -> None:
    db_path = tmp_path / "test.db"
    initialize_database(db_path)
    conn = connect(db_path)
    backup = {**_version_2_backup(), "version": version}

    with pytest.raises(ValueError, match="unsupported backup version"):
        restore_backup(conn, backup)

    conn.close()


@pytest.mark.parametrize(
    "timestamp",
    [
        "2026-07-12",
        "2026-07-12T00:00:00",
        "2026-07-12T00:00:00+00:00",
        "2026-07-12T08:00:00+08:00",
        "2026-07-12t00:00:00Z",
        "2026-02-30T00:00:00Z",
    ],
)
def test_restore_rejects_non_canonical_export_timestamp(
    tmp_path: Path,
    timestamp: str,
) -> None:
    db_path = tmp_path / "test.db"
    initialize_database(db_path)
    conn = connect(db_path)
    backup = {**_version_2_backup(), "exportedAt": timestamp}

    with pytest.raises(ValueError, match="exportedAt"):
        restore_backup(conn, backup)

    conn.close()


@pytest.mark.parametrize(
    "timestamp",
    [
        "2026-01-01",
        "2026-01-01T00:00:00",
        "2026-01-01T00:00:00+00:00",
        "2026-01-01T08:00:00+08:00",
    ],
)
def test_restore_rejects_non_canonical_holiday_timestamp(
    tmp_path: Path,
    timestamp: str,
) -> None:
    db_path = tmp_path / "test.db"
    initialize_database(db_path)
    conn = connect(db_path)
    backup = {
        **_version_2_backup(),
        "holidayCache": {
            "2026": {"holidays": {}, "fetchedAt": timestamp}
        },
    }

    with pytest.raises(ValueError, match="holiday fetchedAt"):
        restore_backup(conn, backup)

    conn.close()


@pytest.mark.parametrize(
    "year",
    ["026", "02026", "２０２６", "1999", "2101"],
)
def test_restore_rejects_non_canonical_holiday_year(
    tmp_path: Path,
    year: str,
) -> None:
    db_path = tmp_path / "test.db"
    initialize_database(db_path)
    conn = connect(db_path)
    backup = {
        **_version_2_backup(),
        "holidayCache": {
            year: {"holidays": {}, "fetchedAt": "2026-01-01T00:00:00Z"}
        },
    }

    with pytest.raises(ValueError, match="holiday cache year"):
        restore_backup(conn, backup)

    conn.close()


@pytest.mark.parametrize("month_day", ["1-01", "01-1", "02-29", "13-01"])
def test_restore_rejects_non_canonical_or_invalid_holiday_date(
    tmp_path: Path,
    month_day: str,
) -> None:
    db_path = tmp_path / "test.db"
    initialize_database(db_path)
    conn = connect(db_path)
    backup = {
        **_version_2_backup(),
        "holidayCache": {
            "2026": {
                "holidays": {
                    month_day: {"name": "Holiday", "isOffDay": True}
                },
                "fetchedAt": "2026-01-01T00:00:00Z",
            }
        },
    }

    with pytest.raises(ValueError, match="holiday date"):
        restore_backup(conn, backup)

    conn.close()


@pytest.mark.parametrize("counts", ["true", "false", 1, 0])
def test_restore_rejects_coercible_counts_values(
    tmp_path: Path,
    counts: object,
) -> None:
    db_path = tmp_path / "test.db"
    initialize_database(db_path)
    conn = connect(db_path)
    backup = {
        **_version_2_backup(),
        "entries": {
            "2026-07-12": {
                "in": "08:00",
                "out": "18:30",
                "counts": counts,
            }
        },
    }

    with pytest.raises(ValueError):
        restore_backup(conn, backup)

    conn.close()


@pytest.mark.parametrize("is_off_day", ["true", "false", 1, 0])
def test_restore_rejects_coercible_is_off_day_values(
    tmp_path: Path,
    is_off_day: object,
) -> None:
    db_path = tmp_path / "test.db"
    initialize_database(db_path)
    conn = connect(db_path)
    backup = {
        **_version_2_backup(),
        "holidayCache": {
            "2026": {
                "holidays": {
                    "01-01": {
                        "name": "New Year",
                        "isOffDay": is_off_day,
                    }
                },
                "fetchedAt": "2026-01-01T00:00:00Z",
            }
        },
    }

    with pytest.raises(ValueError, match="holiday entry"):
        restore_backup(conn, backup)

    conn.close()


def test_version_2_restores_non_empty_holiday_cache(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    initialize_database(db_path)
    conn = connect(db_path)
    backup = {
        **_version_2_backup(),
        "entries": {
            "2028-02-29": {"in": "08:00", "out": "18:30", "counts": True}
        },
        "preferences": {"theme": "teal"},
        "holidayCache": {
            "2028": {
                "holidays": {
                    "02-29": {"name": "Leap Day", "isOffDay": False}
                },
                "fetchedAt": "2028-01-01T00:00:00.123Z",
            }
        },
    }

    summary = restore_backup(conn, backup)

    assert summary == {"version": 2, "entries": 1, "holidayYears": 1}
    restored = build_backup(conn)
    assert restored["entries"] == backup["entries"]
    assert restored["preferences"] == backup["preferences"]
    assert restored["holidayCache"] == backup["holidayCache"]
    conn.close()
