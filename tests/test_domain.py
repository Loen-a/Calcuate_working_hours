from datetime import date, time

from workhours.domain import (
    DayOverride,
    ForecastSettings,
    PeriodMode,
    WorkEntry,
    build_forecast,
    is_workday,
    period_workdays,
)


def test_calendar_overrides_default_weekday_rules():
    overrides = {
        date(2026, 7, 1): DayOverride.HOLIDAY,
        date(2026, 7, 4): DayOverride.WORKDAY,
    }

    assert is_workday(date(2026, 7, 1), overrides) is False
    assert is_workday(date(2026, 7, 4), overrides) is True
    assert is_workday(date(2026, 7, 6), overrides) is True
    assert is_workday(date(2026, 7, 5), overrides) is False


def test_month_period_uses_adjusted_workdays():
    overrides = {
        date(2026, 7, 1): DayOverride.HOLIDAY,
        date(2026, 7, 4): DayOverride.WORKDAY,
    }

    days = period_workdays(date(2026, 7, 6), PeriodMode.MONTH, overrides)

    assert date(2026, 7, 1) not in days
    assert date(2026, 7, 4) in days
    assert date(2026, 7, 6) in days


def test_forecast_uses_minimum_day_when_remaining_average_is_lower():
    entries = {
        date(2026, 7, 6): WorkEntry(date(2026, 7, 6), time(9), time(21)),
        date(2026, 7, 7): WorkEntry(date(2026, 7, 7), time(9), time(21)),
        date(2026, 7, 8): WorkEntry(date(2026, 7, 8), time(9), time(21)),
        date(2026, 7, 9): WorkEntry(date(2026, 7, 9), time(9), time(21)),
    }

    forecast = build_forecast(
        reference_date=date(2026, 7, 10),
        entries=entries,
        overrides={},
        settings=ForecastSettings(period=PeriodMode.WEEK),
    )

    today = forecast.days[date(2026, 7, 10)]
    assert forecast.target_minutes == 45 * 60
    assert forecast.completed_minutes == 40 * 60
    assert today.recommended_minutes == 8 * 60
    assert today.reason == "minimum_day"


def test_forecast_marks_goal_met_but_still_recommends_minimum_workday():
    entries = {
        date(2026, 7, 6): WorkEntry(date(2026, 7, 6), time(9), time(22, 30)),
        date(2026, 7, 7): WorkEntry(date(2026, 7, 7), time(9), time(22, 30)),
        date(2026, 7, 8): WorkEntry(date(2026, 7, 8), time(9), time(22, 30)),
        date(2026, 7, 9): WorkEntry(date(2026, 7, 9), time(9), time(22, 30)),
    }

    forecast = build_forecast(
        reference_date=date(2026, 7, 10),
        entries=entries,
        overrides={},
        settings=ForecastSettings(period=PeriodMode.WEEK),
    )

    assert forecast.goal_met is True
    assert forecast.days[date(2026, 7, 10)].recommended_minutes == 8 * 60
    assert forecast.days[date(2026, 7, 10)].reason == "goal_met_minimum"


def test_open_entry_gets_suggested_end_time_with_lunch_excluded():
    entries = {
        date(2026, 7, 6): WorkEntry(date(2026, 7, 6), time(9, 30), None),
    }

    forecast = build_forecast(
        reference_date=date(2026, 7, 6),
        entries=entries,
        overrides={},
        settings=ForecastSettings(period=PeriodMode.WEEK),
    )

    assert forecast.days[date(2026, 7, 6)].recommended_minutes == 9 * 60
    assert forecast.days[date(2026, 7, 6)].suggested_end == time(20, 30)
