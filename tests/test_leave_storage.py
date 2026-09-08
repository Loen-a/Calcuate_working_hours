import sqlite3
from datetime import date, time

import pytest

from workhours.domain import DayOverride, WorkEntry
from workhours.storage import WorkHoursStore


def test_leave_is_independent_of_punches_and_manual_calendar(tmp_path):
    store = WorkHoursStore(tmp_path / "hours.sqlite3")
    saturday = date(2026, 9, 12)
    entry = WorkEntry(saturday, time(8), time(18, 30))
    store.save_entry(entry)
    store.set_override(saturday, DayOverride.WORKDAY)
    store.set_leave(saturday, True)
    store.set_leave(saturday, True)
    store.set_leave(date(2026, 10, 1), True)
    assert store.list_leave_days(date(2026, 9, 1), date(2026, 9, 30)) == {saturday}

    store.set_leave(saturday, False)
    store.set_leave(saturday, False)
    assert store.list_leave_days(saturday, saturday) == set()
    assert store.get_entry(saturday) == entry
    assert store.list_overrides(saturday, saturday) == {saturday: DayOverride.WORKDAY}


def test_deleting_punch_preserves_leave_and_manual_override(tmp_path):
    store = WorkHoursStore(tmp_path / "hours.sqlite3")
    day = date(2026, 9, 12)
    store.save_entry(WorkEntry(day, time(8)))
    store.set_override(day, DayOverride.WORKDAY)
    store.set_leave(day, True)
    store.delete_entry(day)
    store.delete_entry(day)
    assert store.get_entry(day) is None
    assert store.list_leave_days(day, day) == {day}
    assert store.list_overrides(day, day)[day] == DayOverride.WORKDAY


def test_theme_and_holiday_cache_survive_reopening(tmp_path):
    path = tmp_path / "hours.sqlite3"
    store = WorkHoursStore(path)
    assert store.get_theme() == "cool"
    assert store.get_holiday_cache(2026) is None
    store.set_theme("teal")
    with pytest.raises(ValueError):
        store.set_theme("invalid")
    holidays = {"10-01": {"name": "国庆节", "isOffDay": True}}
    fetched_at = "2026-09-08T12:00:00Z"
    store.set_holiday_cache(2026, holidays, fetched_at)
    reopened = WorkHoursStore(path)
    assert reopened.get_theme() == "teal"
    assert reopened.get_holiday_cache(2026) == (holidays, fetched_at)
    assert reopened.get_holiday_cache(2027) is None


def test_opening_original_schema_adds_tables_without_changing_existing_data(tmp_path):
    path = tmp_path / "old.sqlite3"
    with sqlite3.connect(path) as conn:
        conn.executescript("""
            CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE entries (
                work_date TEXT PRIMARY KEY, start_time TEXT,
                end_time TEXT, lunch_minutes INTEGER
            );
            CREATE TABLE calendar_overrides (
                work_date TEXT PRIMARY KEY,
                kind TEXT NOT NULL CHECK (kind IN ('holiday', 'workday'))
            );
            INSERT INTO entries VALUES ('2026-09-12', '08:00', NULL, NULL);
            INSERT INTO calendar_overrides VALUES ('2026-09-12', 'workday');
            INSERT INTO settings VALUES ('period', 'month');
        """)
    store = WorkHoursStore(path)
    day = date(2026, 9, 12)
    store.set_leave(day, True)
    assert store.get_entry(day) == WorkEntry(day, time(8))
    assert store.list_overrides(day, day) == {day: DayOverride.WORKDAY}
    assert store.get_settings().period.value == "month"
    assert len(store.list_non_working_intervals()) == 2
    assert len(WorkHoursStore(path).list_non_working_intervals()) == 2
