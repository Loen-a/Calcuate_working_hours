from datetime import date, time

from workhours.domain import (
    DayOverride,
    ForecastSettings,
    PeriodMode,
    WorkEntry,
    build_forecast,
)


SETTINGS = ForecastSettings(
    period=PeriodMode.MONTH,
    non_working_intervals=(),
)


def test_month_balance_accumulates_signed_daily_differences():
    entries = {
        date(2026, 7, 1): WorkEntry(date(2026, 7, 1), time(9), time(18, 10)),
        date(2026, 7, 2): WorkEntry(date(2026, 7, 2), time(9), time(17, 20)),
        date(2026, 7, 3): WorkEntry(date(2026, 7, 3), time(9), time(18)),
        date(2026, 7, 6): WorkEntry(date(2026, 7, 6), time(9), time(18, 30)),
    }

    forecast = build_forecast(
        reference_date=date(2026, 7, 6),
        entries=entries,
        overrides={},
        settings=SETTINGS,
    )

    assert forecast.days[date(2026, 7, 1)].daily_balance_minutes == 10
    assert forecast.days[date(2026, 7, 1)].cumulative_balance_minutes == 10
    assert forecast.days[date(2026, 7, 2)].daily_balance_minutes == -40
    assert forecast.days[date(2026, 7, 2)].cumulative_balance_minutes == -30
    assert forecast.days[date(2026, 7, 3)].daily_balance_minutes == 0
    assert forecast.days[date(2026, 7, 3)].cumulative_balance_minutes == -30
    assert forecast.days[date(2026, 7, 6)].daily_balance_minutes == 30
    assert forecast.days[date(2026, 7, 6)].cumulative_balance_minutes == 0


def test_missing_or_open_entries_have_no_balance_display_value():
    entries = {
        date(2026, 7, 6): WorkEntry(date(2026, 7, 6), time(9), None),
    }

    forecast = build_forecast(
        reference_date=date(2026, 7, 6),
        entries=entries,
        overrides={},
        settings=SETTINGS,
    )

    assert forecast.days[date(2026, 7, 6)].daily_balance_minutes is None
    assert forecast.days[date(2026, 7, 6)].cumulative_balance_minutes is None
    assert forecast.days[date(2026, 7, 7)].daily_balance_minutes is None
    assert forecast.days[date(2026, 7, 7)].cumulative_balance_minutes is None


def test_week_balance_includes_prior_workdays_from_same_month():
    entries = {
        date(2026, 7, 1): WorkEntry(date(2026, 7, 1), time(9), time(18, 10)),
        date(2026, 7, 2): WorkEntry(date(2026, 7, 2), time(9), time(17, 20)),
        date(2026, 7, 6): WorkEntry(date(2026, 7, 6), time(9), time(18, 30)),
    }

    forecast = build_forecast(
        reference_date=date(2026, 7, 6),
        entries=entries,
        overrides={},
        settings=ForecastSettings(
            period=PeriodMode.WEEK,
            non_working_intervals=(),
        ),
    )

    assert date(2026, 7, 1) not in forecast.days
    assert forecast.days[date(2026, 7, 6)].daily_balance_minutes == 30
    assert forecast.days[date(2026, 7, 6)].cumulative_balance_minutes == 0


def test_balance_resets_for_each_natural_month_and_respects_overrides():
    july_entry = WorkEntry(date(2026, 7, 31), time(9), time(19))
    august_entry = WorkEntry(date(2026, 8, 3), time(9), time(17, 50))
    adjusted_saturday = WorkEntry(date(2026, 8, 1), time(9), time(18, 10))

    forecast = build_forecast(
        reference_date=date(2026, 8, 3),
        entries={
            july_entry.work_date: july_entry,
            august_entry.work_date: august_entry,
            adjusted_saturday.work_date: adjusted_saturday,
        },
        overrides={date(2026, 8, 1): DayOverride.WORKDAY},
        settings=SETTINGS,
    )

    assert forecast.days[date(2026, 8, 1)].daily_balance_minutes == 10
    assert forecast.days[date(2026, 8, 1)].cumulative_balance_minutes == 10
    assert forecast.days[date(2026, 8, 3)].daily_balance_minutes == -10
    assert forecast.days[date(2026, 8, 3)].cumulative_balance_minutes == 0
