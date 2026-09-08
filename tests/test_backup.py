from __future__ import annotations

import copy
import json
import sqlite3
from contextlib import contextmanager
from datetime import date, time

import pytest

from workhours.backup import InvalidBackup, build_backup, restore_backup
from workhours.domain import DayOverride, PeriodMode, WorkEntry
from workhours.storage import WorkHoursStore


def complete_backup():
    return {
        "version": 3,
        "exportedAt": "2026-09-08T00:00:00Z",
        "entries": {
            "2026-09-01": {
                "start_time": "08:30", "end_time": None, "lunch_minutes": None,
            },
            "2026-09-02": {
                "start_time": "21:00", "end_time": "06:00", "lunch_minutes": 0,
            },
        },
        "settings": {"period": "month", "theme": "teal"},
        "nonWorkingIntervals": [
            {"id": 9, "name": "午休", "start_time": "12:15",
             "end_time": "13:00", "enabled": False},
        ],
        "calendarOverrides": {"2026-09-01": "workday", "2026-09-03": "holiday"},
        "leaveDays": ["2026-09-01", "2026-09-04"],
        "holidayCache": {
            "2028": {
                "holidays": {"02-29": {"name": "闰日调休", "isOffDay": False}},
                "fetchedAt": "2026-09-08T00:00:00.123Z",
            },
        },
    }


def snapshot(store):
    result = build_backup(store)
    result.pop("exportedAt")
    return result


def test_complete_round_trip_preserves_punches_leave_and_all_settings(tmp_path):
    source = WorkHoursStore(tmp_path / "source.sqlite3")
    summary = restore_backup(source, complete_backup())
    assert summary == {"version": 3, "entries": 2, "leaveDays": 2, "holidayYears": 1}
    exported = build_backup(source)
    assert exported["exportedAt"].endswith("Z")
    for key, value in complete_backup().items():
        if key != "exportedAt":
            assert exported[key] == value

    destination = WorkHoursStore(tmp_path / "destination.sqlite3")
    restore_backup(destination, json.loads(json.dumps(exported)))
    assert snapshot(destination) == snapshot(source)
    assert destination.get_entry(date(2026, 9, 1)).start == time(8, 30)
    assert destination.get_entry(date(2026, 9, 2)).end == time(6)


def test_v3_classic_theme_round_trip_and_reopen_preserve_all_business_data(tmp_path):
    database = tmp_path / "classic.sqlite3"
    source = WorkHoursStore(database)
    backup = complete_backup()
    backup["settings"]["theme"] = "classic"
    restore_backup(source, backup)

    expected = copy.deepcopy(backup)
    expected.pop("exportedAt")
    assert snapshot(source) == expected
    reopened = WorkHoursStore(database)
    assert reopened.get_theme() == "classic"
    assert snapshot(reopened) == expected

    destination = WorkHoursStore(tmp_path / "classic-restored.sqlite3")
    restore_backup(destination, json.loads(json.dumps(build_backup(reopened))))
    assert snapshot(destination) == expected


def test_v1_import_preserves_current_classic_theme_and_main_settings(tmp_path):
    store = WorkHoursStore(tmp_path / "classic-legacy.sqlite3")
    backup = complete_backup()
    backup["settings"]["theme"] = "classic"
    restore_backup(store, backup)
    expected = snapshot(store)
    expected.update(entries={}, leaveDays=[])

    restore_backup(store, {
        "version": 1, "exportedAt": "2026-09-08T00:00:00Z", "entries": {},
    })

    assert snapshot(store) == expected


def test_v2_classic_theme_is_rejected_atomically(tmp_path):
    store = WorkHoursStore(tmp_path / "unsupported-legacy-theme.sqlite3")
    restore_backup(store, complete_backup())
    before = snapshot(store)
    with pytest.raises(InvalidBackup, match="theme"):
        restore_backup(store, {
            "version": 2, "exportedAt": "2026-09-08T00:00:00Z",
            "entries": {}, "preferences": {"theme": "classic"}, "holidayCache": {},
        })
    assert snapshot(store) == before


def test_empty_intervals_stay_empty_after_reopening_database(tmp_path):
    database = tmp_path / "restore.sqlite3"
    store = WorkHoursStore(database)
    backup = complete_backup()
    backup["nonWorkingIntervals"] = []
    restore_backup(store, backup)
    assert WorkHoursStore(database).list_non_working_intervals() == []


@pytest.mark.parametrize("version,theme", [(1, None), (2, "cool"), (2, "teal")])
def test_legacy_import_replaces_punches_and_leave_but_preserves_main_settings(tmp_path, version, theme):
    store = WorkHoursStore(tmp_path / "legacy.sqlite3")
    restore_backup(store, complete_backup())
    before = snapshot(store)
    legacy = {
        "version": version,
        "exportedAt": "2026-09-08T00:00:00Z",
        "entries": {
            "2026-09-05": {"in": "00:00", "out": "00:00", "leave": True},
            "2026-09-06": {"in": "08:30", "out": "18:30", "leave": True},
            "2026-09-07": {"in": "08:40", "out": "18:40", "counts": None},
        },
    }
    if version == 2:
        legacy.update(preferences={"theme": theme}, holidayCache={})
    result = restore_backup(store, legacy)
    after = snapshot(store)
    assert result == {"version": version, "entries": 2, "leaveDays": 2, "holidayYears": 0}
    assert after["leaveDays"] == ["2026-09-05", "2026-09-06"]
    assert set(after["entries"]) == {"2026-09-06", "2026-09-07"}
    assert after["entries"]["2026-09-06"] == {
        "start_time": "08:30", "end_time": "18:30", "lunch_minutes": None,
    }
    assert after["settings"]["period"] == "month"
    assert after["nonWorkingIntervals"] == before["nonWorkingIntervals"]
    assert after["calendarOverrides"] == before["calendarOverrides"]
    assert after["settings"]["theme"] == (theme if version == 2 else "teal")
    assert after["holidayCache"] == ({} if version == 2 else before["holidayCache"])


@pytest.mark.parametrize("counts", [True, False, 0, 1, "false", []])
def test_legacy_counts_is_rejected_without_changing_any_data(tmp_path, counts):
    store = WorkHoursStore(tmp_path / "counts.sqlite3")
    restore_backup(store, complete_backup())
    before = snapshot(store)
    backup = {
        "version": 1, "exportedAt": "2026-09-08T00:00:00Z",
        "entries": {"2026-09-05": {"in": "08:00", "out": "18:00", "counts": counts}},
    }
    with pytest.raises(InvalidBackup, match="counts.*不兼容"):
        restore_backup(store, backup)
    assert snapshot(store) == before


@pytest.mark.parametrize("version", [1, 2])
@pytest.mark.parametrize("start,end", [("08:00", "00:00"), ("00:00", "18:30")])
def test_legacy_leave_with_one_midnight_placeholder_is_rejected_atomically(tmp_path, version, start, end):
    store = WorkHoursStore(tmp_path / "ambiguous-leave.sqlite3")
    restore_backup(store, complete_backup())
    before = snapshot(store)
    backup = {
        "version": version, "exportedAt": "2026-09-08T00:00:00Z",
        "entries": {"2026-09-05": {"in": start, "out": end, "leave": True}},
    }
    if version == 2:
        backup.update(preferences={"theme": "cool"}, holidayCache={})
    with pytest.raises(InvalidBackup, match="2026-09-05.*00:00.*歧义"):
        restore_backup(store, backup)
    assert snapshot(store) == before


@pytest.mark.parametrize("start,end", [("21:00", "00:00"), ("00:00", "08:00"), ("00:00", "00:00")])
def test_v3_preserves_real_midnight_punches_while_on_leave(tmp_path, start, end):
    store = WorkHoursStore(tmp_path / "midnight.sqlite3")
    backup = complete_backup()
    backup["entries"]["2026-09-01"] = {
        "start_time": start, "end_time": end, "lunch_minutes": None,
    }
    restore_backup(store, backup)
    assert snapshot(store)["entries"] == backup["entries"]
    assert snapshot(store)["leaveDays"] == backup["leaveDays"]


@pytest.mark.parametrize("version", [2, 3])
def test_empty_annual_holiday_cache_is_rejected_without_changing_data(tmp_path, version):
    store = WorkHoursStore(tmp_path / "empty-year.sqlite3")
    restore_backup(store, complete_backup())
    before = snapshot(store)
    empty_year = {"2026": {"holidays": {}, "fetchedAt": "2026-09-08T00:00:00Z"}}
    backup = complete_backup()
    if version == 2:
        backup = {
            "version": 2, "exportedAt": "2026-09-08T00:00:00Z",
            "entries": {}, "preferences": {"theme": "cool"},
        }
    backup["holidayCache"] = empty_year
    with pytest.raises(InvalidBackup, match="2026.*不能为空"):
        restore_backup(store, backup)
    assert snapshot(store) == before


def test_empty_top_level_holiday_cache_remains_a_valid_full_backup(tmp_path):
    store = WorkHoursStore(tmp_path / "no-cache.sqlite3")
    backup = complete_backup()
    backup["holidayCache"] = {}
    assert restore_backup(store, backup)["holidayYears"] == 0
    assert snapshot(store)["holidayCache"] == {}


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("version",), True),
        (("version",), 3.0),
        (("exportedAt",), "2026-09-08T08:00:00+08:00"),
        (("exportedAt",), "2026-02-30T00:00:00Z"),
        (("entries", "2026-09-01", "start_time"), "8:30"),
        (("entries", "2026-09-01", "start_time"), "24:00"),
        (("entries", "2026-09-01", "lunch_minutes"), True),
        (("entries", "2026-09-01", "lunch_minutes"), -1),
        (("entries",), {"2026-02-30": {"start_time": None, "end_time": None, "lunch_minutes": None}}),
        (("settings", "period"), "year"),
        (("settings", "theme"), "dark"),
        (("nonWorkingIntervals", 0, "id"), True),
        (("nonWorkingIntervals", 0, "id"), -1),
        (("nonWorkingIntervals", 0, "enabled"), 1),
        (("nonWorkingIntervals", 0, "name"), " "),
        (("nonWorkingIntervals", 0, "end_time"), "12:15"),
        (("nonWorkingIntervals", 0, "end_time"), "08:00"),
        (("calendarOverrides", "2026-09-01"), "leave"),
        (("leaveDays",), ["2026-09-01", "2026-09-01"]),
        (("leaveDays",), ["2026-02-30"]),
        (("holidayCache",), {"2026": {"holidays": {"02-29": {"name": "Bad", "isOffDay": True}}, "fetchedAt": "2026-01-01T00:00:00Z"}}),
        (("holidayCache", "2028", "holidays", "02-29", "isOffDay"), 1),
        (("holidayCache", "2028", "fetchedAt"), "2026-01-01"),
    ],
)
def test_invalid_v3_field_rejects_whole_restore(tmp_path, path, value):
    store = WorkHoursStore(tmp_path / "invalid.sqlite3")
    restore_backup(store, complete_backup())
    before = snapshot(store)
    bad = complete_backup()
    target = bad
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(InvalidBackup):
        restore_backup(store, bad)
    assert snapshot(store) == before


@pytest.mark.parametrize("path", [(), ("entries", "2026-09-01"), ("settings",), ("nonWorkingIntervals", 0), ("holidayCache", "2028"), ("holidayCache", "2028", "holidays", "02-29")])
def test_unknown_fields_reject_whole_restore(tmp_path, path):
    store = WorkHoursStore(tmp_path / "unknown.sqlite3")
    bad = complete_backup()
    target = bad
    for key in path:
        target = target[key]
    target["unexpected"] = True
    with pytest.raises(InvalidBackup, match="未知字段"):
        restore_backup(store, bad)


@pytest.mark.parametrize("field", ["entries", "settings", "nonWorkingIntervals", "calendarOverrides", "leaveDays", "holidayCache"])
def test_missing_v3_category_is_rejected_instead_of_erasing_data(tmp_path, field):
    store = WorkHoursStore(tmp_path / "missing.sqlite3")
    backup = complete_backup()
    backup.pop(field)
    with pytest.raises(InvalidBackup):
        restore_backup(store, backup)


def test_duplicate_interval_ids_rejected(tmp_path):
    store = WorkHoursStore(tmp_path / "duplicate.sqlite3")
    backup = complete_backup()
    backup["nonWorkingIntervals"].append(copy.deepcopy(backup["nonWorkingIntervals"][0]))
    with pytest.raises(InvalidBackup, match="重复"):
        restore_backup(store, backup)


def test_late_sqlite_failure_rolls_back_every_category(tmp_path):
    store = WorkHoursStore(tmp_path / "rollback.sqlite3")
    restore_backup(store, complete_backup())
    before = snapshot(store)
    with store._connect() as connection:
        connection.execute("""
            CREATE TRIGGER reject_imported_cache BEFORE INSERT ON holiday_cache
            WHEN NEW.year = 2029 BEGIN
                SELECT RAISE(ABORT, 'simulated write failure');
            END
        """)
    backup = complete_backup()
    backup.update(entries={}, leaveDays=[], calendarOverrides={}, nonWorkingIntervals=[])
    backup["settings"] = {"period": "week", "theme": "cool"}
    backup["holidayCache"] = {"2029": {
        "holidays": {"01-01": {"name": "元旦", "isOffDay": True}},
        "fetchedAt": "2026-09-08T00:00:00Z",
    }}
    with pytest.raises(sqlite3.IntegrityError, match="simulated write failure"):
        restore_backup(store, backup)
    assert snapshot(store) == before


def test_export_uses_single_sqlite_snapshot_during_concurrent_changes(tmp_path, monkeypatch):
    store = WorkHoursStore(tmp_path / "snapshot.sqlite3")
    restore_backup(store, complete_backup())
    before = snapshot(store)
    writer = sqlite3.connect(store.database_path)
    writer.execute("PRAGMA journal_mode = WAL")
    original_connect = store._connect
    modified = False

    @contextmanager
    def connect_with_concurrent_writer():
        nonlocal modified
        with original_connect() as connection:
            def write_after_first_table(statement):
                nonlocal modified
                if modified or not statement.strip().upper().startswith("SELECT"):
                    return
                # The trace hook runs before SELECT. Run a read first to establish
                # the reader snapshot, then commit a separate writer transaction.
                modified = True
                connection.execute("SELECT COUNT(*) FROM entries").fetchone()
                with writer:
                    writer.execute("DELETE FROM entries")
                    writer.execute("UPDATE settings SET value = 'cool' WHERE key = 'theme'")
                    writer.execute("DELETE FROM leave_days")
                    writer.execute("DELETE FROM holiday_cache")
            connection.set_trace_callback(write_after_first_table)
            yield connection

    monkeypatch.setattr(store, "_connect", connect_with_concurrent_writer)
    try:
        assert snapshot(store) == before
        assert modified
    finally:
        writer.close()
    monkeypatch.setattr(store, "_connect", original_connect)
    assert snapshot(store)["entries"] == {}
