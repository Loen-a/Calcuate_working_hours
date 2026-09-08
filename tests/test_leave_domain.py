from datetime import date, time

from workhours.domain import (
    DayOverride,
    ForecastSettings,
    PeriodMode,
    WorkEntry,
    build_forecast,
    period_workdays,
)


def test_leave_excludes_recorded_and_missing_days_and_can_be_cancelled():
    recorded = date(2026, 9, 7)
    missing = date(2026, 9, 8)
    entries = {recorded: WorkEntry(recorded, time(8), time(20))}
    settings = ForecastSettings(period=PeriodMode.MONTH)
    original = build_forecast(date(2026, 9, 9), entries, {}, settings)

    forecast = build_forecast(
        date(2026, 9, 9), entries, {}, settings, leave_days={recorded, missing}
    )

    assert forecast.month_target_minutes == original.month_target_minutes - 1080
    assert forecast.completed_minutes == 0
    assert recorded not in forecast.days
    assert missing not in forecast.missing_history_days
    assert forecast.days[date(2026, 9, 9)].balance_before_minutes == 0
    assert forecast.days[date(2026, 9, 9)].required_minutes == 540
    assert entries[recorded].end == time(20)
    assert build_forecast(date(2026, 9, 9), entries, {}, settings, set()) == original


def test_leave_on_compensating_weekend_preserves_manual_calendar():
    saturday = date(2026, 9, 12)
    overrides = {saturday: DayOverride.WORKDAY}
    assert saturday in period_workdays(saturday, PeriodMode.WEEK, overrides)
    assert saturday not in period_workdays(
        saturday, PeriodMode.WEEK, overrides, leave_days={saturday}
    )
    assert overrides == {saturday: DayOverride.WORKDAY}
    assert saturday in period_workdays(saturday, PeriodMode.WEEK, overrides, set())


def test_prior_week_leave_does_not_create_carryover_debt_or_credit():
    friday = date(2026, 9, 4)
    entries = {friday: WorkEntry(friday, time(8), time(20))}
    forecast = build_forecast(
        date(2026, 9, 8), entries, {}, ForecastSettings(), {friday}
    )
    assert forecast.carryover_minutes == 0
    assert forecast.target_minutes == 5 * 540
    assert forecast.month_completed_minutes == 0


def test_all_remaining_days_on_leave_produce_zero_target_and_projection():
    reference = date(2026, 9, 7)
    leave = set(period_workdays(reference, PeriodMode.MONTH, {}))
    forecast = build_forecast(reference, {}, {}, ForecastSettings(), leave)
    assert forecast.workdays == []
    assert forecast.days == {}
    assert forecast.missing_history_days == []
    assert forecast.target_minutes == forecast.month_target_minutes == 0
    assert forecast.projected_minutes == forecast.remaining_target_minutes == 0
    assert forecast.goal_met
