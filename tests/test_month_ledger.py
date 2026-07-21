from datetime import date, time

from workhours.domain import (
    ForecastSettings,
    PeriodMode,
    WorkEntry,
    build_forecast,
    period_workdays,
)


def test_weekly_forecast_carries_prior_month_deficit_into_current_week():
    entries = {
        date(2026, 7, day): WorkEntry(
            date(2026, 7, day),
            time(9),
            time(18, 30),
        )
        for day in (1, 2, 3, 6, 7, 8, 9, 10)
    }

    forecast = build_forecast(
        reference_date=date(2026, 7, 13),
        entries=entries,
        overrides={},
        settings=ForecastSettings(period=PeriodMode.WEEK),
    )

    assert forecast.base_target_minutes == 45 * 60
    assert forecast.carryover_minutes == 8 * 60
    assert forecast.target_minutes == 53 * 60
    assert forecast.days[date(2026, 7, 13)].recommended_minutes == 10 * 60 + 36


def test_weekly_forecast_uses_prior_surplus_but_keeps_daily_minimum():
    entries = {
        date(2026, 7, day): WorkEntry(
            date(2026, 7, day),
            time(9),
            time(21),
        )
        for day in (1, 2, 3, 6, 7, 8, 9, 10)
    }

    forecast = build_forecast(
        reference_date=date(2026, 7, 13),
        entries=entries,
        overrides={},
        settings=ForecastSettings(period=PeriodMode.WEEK),
    )

    assert forecast.carryover_minutes == -8 * 60
    assert forecast.target_minutes == 37 * 60
    assert forecast.days[date(2026, 7, 13)].recommended_minutes == 8 * 60


def test_monthly_forecast_spreads_month_balance_to_month_end():
    entries = {
        date(2026, 7, day): WorkEntry(
            date(2026, 7, day),
            time(9),
            time(18, 30),
        )
        for day in (1, 2, 3, 6, 7, 8, 9, 10)
    }

    forecast = build_forecast(
        reference_date=date(2026, 7, 13),
        entries=entries,
        overrides={},
        settings=ForecastSettings(period=PeriodMode.MONTH),
    )

    assert forecast.month_target_minutes == 23 * 9 * 60
    assert forecast.month_completed_minutes == 64 * 60
    assert forecast.remaining_target_minutes == 143 * 60
    assert forecast.days[date(2026, 7, 13)].recommended_minutes == 9 * 60 + 32


def test_week_period_is_clipped_to_reference_month():
    days = period_workdays(date(2026, 7, 1), PeriodMode.WEEK, {})

    assert days == [date(2026, 7, 1), date(2026, 7, 2), date(2026, 7, 3)]


def test_missing_past_records_are_neutral_in_monthly_planning():
    forecast = build_forecast(
        reference_date=date(2026, 7, 13),
        entries={},
        overrides={},
        settings=ForecastSettings(period=PeriodMode.MONTH),
    )

    assert forecast.missing_history_days == [
        date(2026, 7, 1),
        date(2026, 7, 2),
        date(2026, 7, 3),
        date(2026, 7, 6),
        date(2026, 7, 7),
        date(2026, 7, 8),
        date(2026, 7, 9),
        date(2026, 7, 10),
    ]
    assert forecast.remaining_target_minutes == 15 * 9 * 60
    assert forecast.days[date(2026, 7, 13)].recommended_minutes == 9 * 60
    assert forecast.days[date(2026, 7, 10)].reason == "missing_entry"
    assert forecast.days[date(2026, 7, 10)].recommended_minutes is None
