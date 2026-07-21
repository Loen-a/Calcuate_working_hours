from datetime import date, time

from workhours.domain import DayOverride, PeriodMode, WorkEntry
from workhours.storage import WorkHoursStore


def test_store_uses_default_settings(tmp_path):
    store = WorkHoursStore(tmp_path / "workhours.sqlite3")

    settings = store.get_settings()

    assert settings.period == PeriodMode.WEEK
    assert settings.target_minutes_per_day == 9 * 60
    assert settings.minimum_minutes_per_day == 8 * 60
    assert settings.lunch_minutes == 90


def test_store_persists_period_setting(tmp_path):
    store = WorkHoursStore(tmp_path / "workhours.sqlite3")

    store.set_period(PeriodMode.MONTH)

    assert store.get_settings().period == PeriodMode.MONTH


def test_store_persists_entries(tmp_path):
    store = WorkHoursStore(tmp_path / "workhours.sqlite3")
    entry = WorkEntry(date(2026, 7, 6), time(9, 30), time(20, 0), 90)

    store.save_entry(entry)

    entries = store.list_entries(date(2026, 7, 1), date(2026, 7, 31))
    assert entries == {date(2026, 7, 6): entry}


def test_store_persists_calendar_overrides(tmp_path):
    store = WorkHoursStore(tmp_path / "workhours.sqlite3")

    store.set_override(date(2026, 7, 1), DayOverride.HOLIDAY)
    store.set_override(date(2026, 7, 4), DayOverride.WORKDAY)

    assert store.list_overrides(date(2026, 7, 1), date(2026, 7, 31)) == {
        date(2026, 7, 1): DayOverride.HOLIDAY,
        date(2026, 7, 4): DayOverride.WORKDAY,
    }

    store.delete_override(date(2026, 7, 1))

    assert store.list_overrides(date(2026, 7, 1), date(2026, 7, 31)) == {
        date(2026, 7, 4): DayOverride.WORKDAY,
    }
