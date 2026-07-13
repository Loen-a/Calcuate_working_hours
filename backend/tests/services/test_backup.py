import sqlite3
from pathlib import Path

import pytest

import backend.services.backup as backup_service
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


@pytest.mark.parametrize(
    "extra_location",
    [
        "v1 top level",
        "v2 top level",
        "entry",
        "preferences",
        "holiday year container",
        "holiday item",
    ],
)
def test_restore_rejects_unknown_fields_atomically(
    tmp_path: Path,
    extra_location: str,
) -> None:
    db_path = tmp_path / "test.db"
    initialize_database(db_path)
    conn = connect(db_path)
    with conn:
        upsert_entry(conn, "2026-06-30", "08:00", "18:00", True)
        set_theme(conn, "teal")
        set_holiday_cache(
            conn,
            2026,
            {"01-01": {"name": "Existing", "isOffDay": True}},
            "2026-01-01T00:00:00Z",
        )
    before = (
        list_entries(conn),
        get_theme(conn),
        list_holiday_cache(conn),
    )
    backup: dict[str, object] = {
        "version": 2,
        "exportedAt": "2026-07-12T00:00:00Z",
        "entries": {
            "2026-07-12": {"in": "08:10", "out": "18:40"}
        },
        "preferences": {"theme": "cool"},
        "holidayCache": {
            "2026": {
                "holidays": {
                    "01-02": {"name": "Imported", "isOffDay": False}
                },
                "fetchedAt": "2026-01-02T00:00:00Z",
            }
        },
    }

    if extra_location == "v1 top level":
        backup = {
            "version": 1,
            "exportedAt": backup["exportedAt"],
            "entries": backup["entries"],
            "unexpected": True,
        }
    elif extra_location == "v2 top level":
        backup["unexpected"] = True
    elif extra_location == "entry":
        backup["entries"]["2026-07-12"]["unexpected"] = True  # type: ignore[index]
    elif extra_location == "preferences":
        backup["preferences"]["unexpected"] = True  # type: ignore[index]
    elif extra_location == "holiday year container":
        backup["holidayCache"]["2026"]["unexpected"] = True  # type: ignore[index]
    else:
        backup["holidayCache"]["2026"]["holidays"]["01-02"][  # type: ignore[index]
            "unexpected"
        ] = True

    with pytest.raises(ValueError):
        restore_backup(conn, backup)

    assert (
        list_entries(conn),
        get_theme(conn),
        list_holiday_cache(conn),
    ) == before
    conn.close()


def test_build_backup_reads_one_consistent_sqlite_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "test.db"
    initialize_database(db_path)
    reader = connect(db_path)
    reader.execute("PRAGMA journal_mode = WAL")
    with reader:
        upsert_entry(reader, "2026-07-01", "08:00", "18:00", True)
        set_theme(reader, "cool")
        set_holiday_cache(
            reader,
            2026,
            {"01-01": {"name": "Old", "isOffDay": True}},
            "2026-01-01T00:00:00Z",
        )
    writer = connect(db_path)
    real_list_entries = backup_service.list_entries

    def read_entries_then_write(conn: sqlite3.Connection):
        entries = real_list_entries(conn)
        with writer:
            upsert_entry(writer, "2026-07-02", "09:00", "19:00", False)
            set_theme(writer, "teal")
            set_holiday_cache(
                writer,
                2026,
                {"01-02": {"name": "New", "isOffDay": False}},
                "2026-01-02T00:00:00Z",
            )
        return entries

    monkeypatch.setattr(
        backup_service,
        "list_entries",
        read_entries_then_write,
    )

    backup = build_backup(reader)

    assert backup["entries"] == {
        "2026-07-01": {"in": "08:00", "out": "18:00", "counts": True}
    }
    assert backup["preferences"] == {"theme": "cool"}
    assert backup["holidayCache"] == {
        "2026": {
            "holidays": {"01-01": {"name": "Old", "isOffDay": True}},
            "fetchedAt": "2026-01-01T00:00:00Z",
        }
    }
    assert get_theme(writer) == "teal"
    writer.close()
    reader.close()


def test_build_backup_rolls_back_read_transaction_on_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "test.db"
    initialize_database(db_path)
    conn = connect(db_path)

    def fail(_conn: sqlite3.Connection):
        raise RuntimeError("simulated read failure")

    monkeypatch.setattr(backup_service, "list_entries", fail)

    with pytest.raises(RuntimeError, match="simulated read failure"):
        build_backup(conn)

    assert not conn.in_transaction
    conn.close()
