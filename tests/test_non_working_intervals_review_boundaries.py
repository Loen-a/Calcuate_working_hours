import sqlite3
from datetime import date, datetime, time

import pytest

from workhours.domain import (
    ForecastSettings,
    NonWorkingInterval,
    PeriodMode,
    WorkEntry,
    build_forecast,
    default_non_working_intervals,
    effective_minutes,
)
from workhours.storage import WorkHoursStore
from workhours.web import create_app


def test_equal_clock_times_do_not_count_as_twenty_four_hours():
    entry = WorkEntry(date(2026, 7, 15), time(9), time(9))

    assert effective_minutes(entry, default_non_working_intervals()) == 0


def test_overnight_suggested_end_exposes_next_day_offset():
    work_date = date(2026, 7, 6)
    forecast = build_forecast(
        reference_date=work_date,
        entries={work_date: WorkEntry(work_date, time(23), None)},
        overrides={},
        settings=ForecastSettings(period=PeriodMode.WEEK),
    )

    day = forecast.days[work_date]
    assert day.suggested_end == time(8)
    assert day.suggested_end_day_offset == 1


def test_web_hides_overnight_suggested_end(tmp_path):
    app = create_app(
        database_path=tmp_path / "workhours.sqlite3",
        today_provider=lambda: date(2026, 7, 6),
        now_provider=lambda: datetime(2026, 7, 6, 23),
    )
    app.config.update(TESTING=True)

    response = app.test_client().post(
        "/entries",
        data={
            "work_date": "2026-07-06",
            "start_time": "23:00",
            "end_time": "",
        },
        follow_redirects=True,
    )

    body = response.get_data(as_text=True)
    assert "<th>建议下班</th>" not in body
    assert "次日 08:00" not in body


def test_store_rejects_second_level_intervals(tmp_path):
    store = WorkHoursStore(tmp_path / "workhours.sqlite3")

    with pytest.raises(ValueError):
        store.save_non_working_interval(
            NonWorkingInterval(
                None,
                "秒级规则",
                time(12, 0, 30),
                time(12, 0, 45),
            )
        )


def test_store_rejects_deleting_missing_interval(tmp_path):
    store = WorkHoursStore(tmp_path / "workhours.sqlite3")

    with pytest.raises(ValueError):
        store.delete_non_working_interval(999)


def test_old_database_is_migrated_without_losing_entries(tmp_path):
    database_path = tmp_path / "workhours.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE entries (
                work_date TEXT PRIMARY KEY,
                start_time TEXT,
                end_time TEXT,
                lunch_minutes INTEGER
            );
            CREATE TABLE calendar_overrides (
                work_date TEXT PRIMARY KEY,
                kind TEXT NOT NULL
            );
            INSERT INTO entries VALUES ('2026-07-06', '09:00', '18:30', 90);
            """
        )

    store = WorkHoursStore(database_path)

    assert store.get_entry(date(2026, 7, 6)) == WorkEntry(
        date(2026, 7, 6),
        time(9),
        time(18, 30),
        90,
    )
    assert len(store.list_non_working_intervals()) == 2
