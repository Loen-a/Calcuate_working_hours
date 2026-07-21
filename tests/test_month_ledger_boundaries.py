from datetime import date, time

from workhours.domain import (
    DayOverride,
    ForecastSettings,
    PeriodMode,
    WorkEntry,
    build_forecast,
)


def test_first_week_of_month_does_not_carry_previous_month_entries():
    entries = {
        date(2026, 6, 29): WorkEntry(
            date(2026, 6, 29),
            time(9),
            time(22, 30),
        ),
        date(2026, 6, 30): WorkEntry(
            date(2026, 6, 30),
            time(9),
            time(22, 30),
        ),
    }

    forecast = build_forecast(
        reference_date=date(2026, 7, 1),
        entries=entries,
        overrides={},
        settings=ForecastSettings(period=PeriodMode.WEEK),
    )

    assert forecast.period_start == date(2026, 7, 1)
    assert forecast.carryover_minutes == 0
    assert forecast.target_minutes == 3 * 9 * 60


def test_weekly_carry_uses_holidays_and_adjusted_workdays():
    overrides = {
        date(2026, 7, 1): DayOverride.HOLIDAY,
        date(2026, 7, 4): DayOverride.WORKDAY,
    }
    entries = {
        date(2026, 7, day): WorkEntry(
            date(2026, 7, day),
            time(9),
            time(18, 30),
        )
        for day in (2, 3, 4)
    }

    forecast = build_forecast(
        reference_date=date(2026, 7, 6),
        entries=entries,
        overrides=overrides,
        settings=ForecastSettings(period=PeriodMode.WEEK),
    )

    assert forecast.carryover_minutes == 3 * 60
    assert forecast.target_minutes == 48 * 60
    assert forecast.days[date(2026, 7, 6)].recommended_minutes == 9 * 60 + 36
